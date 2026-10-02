<?php

declare(strict_types=1);

namespace LombokCLIParse;

/**
 * A command-line application or subcommand definition (builder). The same
 * input gives the same result, error message and help text as the Rust,
 * TypeScript, Python and Go ports (docs/SPEC_LombokCLIParse_v0.2.0.md).
 */
final class App
{
    public const MAX_SAFE_INTEGER = 9007199254740991;

    private const BOOLS = ['true' => true, '1' => true, 'yes' => true, 'on' => true, 'false' => false, '0' => false, 'no' => false, 'off' => false];
    private const PLACEHOLDER = ['string' => '<VALUE>', 'int' => '<INT>', 'float' => '<FLOAT>', 'bool' => '<BOOL>'];

    private ?string $version = null;
    /** @var list<array{name: string, help: string, type: ArgType, required: bool}> */
    private array $positionals = [];
    /** @var list<array{kind: string, name: string, help: string, short: ?string, type?: ArgType, default?: ?string, env?: ?string}> */
    private array $args = [];
    /** @var list<App> */
    private array $subs = [];

    public function __construct(private readonly string $name, private readonly string $description = '')
    {
    }

    /** Sets the version; enables --version. */
    public function version(string $v): self
    {
        $this->version = $v;
        return $this;
    }

    /** Adds a positional argument (filled in definition order). */
    public function positional(string $name, string $help, ArgType $type = ArgType::STR, bool $required = false): self
    {
        $this->positionals[] = ['name' => $name, 'help' => $help, 'type' => $type, 'required' => $required];
        return $this;
    }

    /** Adds a boolean flag, --name or -c. */
    public function flag(string $name, string $help, ?string $short = null): self
    {
        $this->args[] = ['kind' => 'flag', 'name' => $name, 'help' => $help, 'short' => $short];
        return $this;
    }

    /** Adds an option taking a value; when absent, $envVar and then $default are used. */
    public function option(string $name, string $help, ArgType $type = ArgType::STR, ?string $short = null, ?string $default = null, ?string $envVar = null): self
    {
        $this->args[] = ['kind' => 'option', 'name' => $name, 'help' => $help, 'short' => $short, 'type' => $type, 'default' => $default, 'env' => $envVar];
        return $this;
    }

    /** Adds a subcommand. An app with subcommands has no positional arguments. */
    public function subcommand(App $sub): self
    {
        $this->subs[] = $sub;
        return $this;
    }

    /** Same as subcommand() (0.1 name). */
    public function sub(App $sub): self
    {
        return $this->subcommand($sub);
    }

    /** Parses $raw as $type; null when the text is not valid for the type. */
    public static function parseValue(ArgType $type, string $raw): ?Value
    {
        switch ($type) {
            case ArgType::STR:
                return Value::str($raw);
            case ArgType::INT:
                if (preg_match('/^[+-]?[0-9]+$/D', $raw) !== 1 || strlen(ltrim(ltrim($raw, '+-'), '0')) > 16) {
                    return null;
                }
                $n = (int) $raw;
                return abs($n) <= self::MAX_SAFE_INTEGER ? Value::int($n) : null;
            case ArgType::FLOAT:
                if (preg_match('/^[+-]?([0-9]+(\.[0-9]*)?|\.[0-9]+)([eE][+-]?[0-9]+)?$/D', $raw) !== 1) {
                    return null;
                }
                $f = (float) $raw;
                return is_finite($f) ? Value::float($f) : null;
            default:
                if (preg_match('/^[\x00-\x7f]*$/D', $raw) !== 1) {
                    return null;
                }
                $b = self::BOOLS[strtolower($raw)] ?? null;
                return $b === null ? null : Value::bool($b);
        }
    }

    private static function validName(string $n): bool
    {
        return preg_match('/^[A-Za-z0-9][A-Za-z0-9_-]*$/D', $n) === 1;
    }

    private static function defErr(string $arg, string $reason): ParseError
    {
        return new ParseError('INVALID_DEFINITION', $arg, reason: $reason);
    }

    /** Checks the rules of SPEC section 2; throws INVALID_DEFINITION. */
    public function validate(): void
    {
        $names = [];
        $shorts = [];
        foreach ([...$this->positionals, ...$this->args] as $a) {
            $n = $a['name'];
            if (!self::validName($n)) {
                throw self::defErr($n, 'invalid name');
            }
            if ($n === 'help' || ($n === 'version' && $this->version !== null)) {
                throw self::defErr($n, 'reserved name');
            }
            if (isset($names[$n])) {
                throw self::defErr($n, 'duplicate name');
            }
            $names[$n] = true;
            $s = $a['short'] ?? null;
            if ($s !== null) {
                if (preg_match('/^[A-Za-z]$/D', $s) !== 1) {
                    throw self::defErr($s, 'invalid short');
                }
                if (isset($shorts[$s])) {
                    throw self::defErr($s, 'duplicate short');
                }
                $shorts[$s] = true;
            }
            if (($a['kind'] ?? '') === 'option' && $a['default'] !== null && self::parseValue($a['type'], $a['default']) === null) {
                throw self::defErr($n, 'invalid default');
            }
        }
        $seenOptional = false;
        foreach ($this->positionals as $p) {
            if ($p['required'] && $seenOptional) {
                throw self::defErr($p['name'], 'required after optional');
            }
            $seenOptional = $seenOptional || !$p['required'];
        }
        if ($this->subs !== [] && $this->positionals !== []) {
            throw self::defErr($this->subs[0]->name, 'positionals with subcommands');
        }
        $subNames = [];
        foreach ($this->subs as $s) {
            if (!self::validName($s->name)) {
                throw self::defErr($s->name, 'invalid name');
            }
            if (isset($subNames[$s->name])) {
                throw self::defErr($s->name, 'duplicate name');
            }
            $subNames[$s->name] = true;
            $s->validate();
        }
    }

    private static function cpLen(string $s): int
    {
        return (int) preg_match_all('/./us', $s);
    }

    /** @param list<string> $parts */
    private static function join(array $parts): string
    {
        return implode(' ', array_values(array_filter($parts, static fn ($p) => $p !== '')));
    }

    /** @param list<array{0: string, 1: string}> $rows */
    private static function section(string $title, array $rows): string
    {
        $width = max(array_map(static fn ($r) => self::cpLen($r[0]), $rows));
        $out = $title . ":\n";
        foreach ($rows as [$left, $help]) {
            $out .= $help !== '' ? '    ' . $left . str_repeat(' ', $width - self::cpLen($left) + 2) . $help . "\n" : '    ' . $left . "\n";
        }
        return $out;
    }

    /** The help text (SPEC section 5) as shown for --help. */
    public function help(): string
    {
        return $this->helpAt($this->name);
    }

    private function helpAt(string $path): string
    {
        $out = $this->name . ($this->version !== null ? ' ' . $this->version : '') . "\n";
        if ($this->description !== '') {
            $out .= $this->description . "\n";
        }
        $out .= "\nUSAGE:\n    " . $path . ' [OPTIONS]';
        if ($this->subs !== []) {
            $out .= ' <COMMAND>';
        }
        foreach ($this->positionals as $p) {
            $n = strtoupper($p['name']);
            $out .= $p['required'] ? " <$n>" : " [$n]";
        }
        $out .= "\n";
        if ($this->positionals !== []) {
            $rows = array_map(static fn ($p) => ['<' . strtoupper($p['name']) . '>', self::join([$p['help'], $p['required'] ? '(required)' : ''])], $this->positionals);
            $out .= "\n" . self::section('ARGS', $rows);
        }
        if ($this->subs !== []) {
            $out .= "\n" . self::section('COMMANDS', array_map(static fn (App $s) => [$s->name, $s->description], $this->subs));
        }
        $rows = [];
        foreach ($this->args as $a) {
            $left = ($a['short'] !== null ? '-' . $a['short'] . ', ' : '    ') . '--' . $a['name'];
            if ($a['kind'] === 'flag') {
                $rows[] = [$left, $a['help']];
                continue;
            }
            $rows[] = [
                $left . ' ' . self::PLACEHOLDER[$a['type']->value],
                self::join([$a['help'], $a['default'] !== null ? '[default: ' . $a['default'] . ']' : '', $a['env'] !== null ? '[env: ' . $a['env'] . ']' : '']),
            ];
        }
        $rows[] = ['    --help', 'Print help'];
        if ($this->version !== null) {
            $rows[] = ['    --version', 'Print version'];
        }
        return $out . "\n" . self::section('OPTIONS', $rows);
    }

    /**
     * Parses a full command line ($argv[0] is the program name) with the
     * process environment (getenv) for fallback values.
     *
     * @param list<string> $argv
     */
    public function parse(array $argv): Matches
    {
        return $this->parseWithEnv(array_slice($argv, 1), static function (string $k): ?string {
            $v = getenv($k);
            return $v === false ? null : $v;
        });
    }

    /**
     * Parses $tokens (without the program name) with an explicit environment:
     * an array of name => value, or a callable returning ?string.
     *
     * @param list<string> $tokens
     * @param array<string, string>|callable(string): ?string $env
     */
    public function parseWithEnv(array $tokens, array|callable $env = []): Matches
    {
        $this->validate();
        $lookup = is_callable($env) ? $env : static fn (string $k): ?string => array_key_exists($k, $env) ? (string) $env[$k] : null;
        return $this->parseTokens(array_values($tokens), $lookup, $this->name);
    }

    /** Parses $_SERVER['argv']. */
    public function parseEnv(): Matches
    {
        return $this->parse($_SERVER['argv'] ?? []);
    }

    /**
     * Parses $_SERVER['argv']; prints help or version and exits with 0, or
     * prints the error to STDERR and exits with 2.
     */
    public function run(): Matches
    {
        try {
            return $this->parseEnv();
        } catch (ParseError $e) {
            if ($e->isInfo()) {
                echo $e->text;
                exit(0);
            }
            fwrite(STDERR, 'error: ' . $e->getMessage() . "\n");
            exit(2);
        }
    }

    private static function set(Matches $m, array $a, string $raw, string $arg): void
    {
        $v = self::parseValue($a['type'], $raw);
        if ($v === null) {
            throw new ParseError('INVALID_VALUE', $arg, value: $raw);
        }
        $m->setValue($a['name'], $v);
    }

    private function findArg(string $key, string $value): ?array
    {
        foreach ($this->args as $a) {
            if ($a[$key] === $value) {
                return $a;
            }
        }
        return null;
    }

    /**
     * @param list<string> $tokens
     * @param callable(string): ?string $env
     */
    private function parseTokens(array $tokens, callable $env, string $path): Matches
    {
        $m = new Matches();
        $posIdx = 0;
        $i = 0;
        $afterDD = false;
        $count = count($tokens);
        while ($i < $count) {
            $tok = $tokens[$i];
            $i++;
            if (!$afterDD) {
                if ($tok === '--') {
                    $afterDD = true;
                    continue;
                }
                if ($tok === '--help') {
                    throw new ParseError('HELP', text: $this->helpAt($path));
                }
                if ($tok === '--version' && $this->version !== null) {
                    throw new ParseError('VERSION', text: $this->name . ' ' . $this->version . "\n");
                }
                if (str_starts_with($tok, '--')) {
                    $body = substr($tok, 2);
                    $eq = strpos($body, '=');
                    $name = $eq === false ? $body : substr($body, 0, $eq);
                    $inline = $eq === false ? null : substr($body, $eq + 1);
                    $arg = '--' . $name;
                    $a = $this->findArg('name', $name);
                    if ($a === null) {
                        throw new ParseError('UNKNOWN_ARGUMENT', $arg);
                    }
                    if ($a['kind'] === 'flag') {
                        if ($inline !== null) {
                            throw new ParseError('FLAG_TAKES_NO_VALUE', $arg);
                        }
                        $m->setFlag($a['name']);
                        continue;
                    }
                    if ($inline === null) {
                        if ($i >= $count) {
                            throw new ParseError('MISSING_VALUE', $arg);
                        }
                        $inline = $tokens[$i++];
                    }
                    self::set($m, $a, $inline, $arg);
                    continue;
                }
                if (strlen($tok) > 1 && $tok[0] === '-' && strpbrk($tok[1], '0123456789.') === false) {
                    $cluster = preg_split('//u', substr($tok, 1), -1, PREG_SPLIT_NO_EMPTY) ?: [];
                    foreach ($cluster as $k => $c) {
                        $arg = '-' . $c;
                        $a = $this->findArg('short', $c);
                        if ($a === null) {
                            throw new ParseError('UNKNOWN_ARGUMENT', $arg);
                        }
                        if ($a['kind'] === 'flag') {
                            $m->setFlag($a['name']);
                            continue;
                        }
                        $raw = implode('', array_slice($cluster, $k + 1));
                        if (str_starts_with($raw, '=')) {
                            $raw = substr($raw, 1);
                        } elseif ($raw === '') {
                            if ($i >= $count) {
                                throw new ParseError('MISSING_VALUE', $arg);
                            }
                            $raw = $tokens[$i++];
                        }
                        self::set($m, $a, $raw, $arg);
                        break;
                    }
                    continue;
                }
            }
            if (!$afterDD && $this->subs !== []) {
                $sub = null;
                foreach ($this->subs as $s) {
                    if ($s->name === $tok) {
                        $sub = $s;
                    }
                }
                if ($sub === null) {
                    throw new ParseError('UNKNOWN_SUBCOMMAND', $tok);
                }
                $m->setSubcommand($tok, $sub->parseTokens(array_slice($tokens, $i), $env, $path . ' ' . $tok));
                break;
            }
            if ($posIdx < count($this->positionals)) {
                $p = $this->positionals[$posIdx];
                $v = self::parseValue($p['type'], $tok);
                if ($v === null) {
                    throw new ParseError('INVALID_VALUE', $p['name'], value: $tok);
                }
                $m->setValue($p['name'], $v);
                $posIdx++;
            } elseif ($afterDD) {
                $m->addRest($tok);
            } else {
                throw new ParseError('UNEXPECTED_ARGUMENT', $tok);
            }
        }
        foreach ($this->args as $a) {
            if ($a['kind'] !== 'option' || $m->hasValue($a['name'])) {
                continue;
            }
            $fromEnv = $a['env'] !== null ? $env($a['env']) : null;
            if ($fromEnv !== null) {
                self::set($m, $a, $fromEnv, '--' . $a['name']);
            } elseif ($a['default'] !== null) {
                self::set($m, $a, $a['default'], '--' . $a['name']);
            }
        }
        foreach ($this->positionals as $p) {
            if ($p['required'] && !$m->hasValue($p['name'])) {
                throw new ParseError('MISSING_REQUIRED', $p['name']);
            }
        }
        return $m;
    }
}
