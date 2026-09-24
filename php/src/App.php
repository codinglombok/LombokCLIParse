<?php

declare(strict_types=1);

namespace LombokCLIParse;

/**
 * CLI application builder.
 *
 * Example:
 *   $app = (new App('myapp', 'My application'))
 *       ->version('1.0.0')
 *       ->positional('input', 'Input file', ArgType::STR, required: true)
 *       ->flag('verbose', 'Enable verbose', short: 'v')
 *       ->option('port', 'Port', ArgType::INT, short: 'p', default: '8080');
 *
 *   $matches = $app->parse(['myapp', 'data.txt', '--verbose', '-p', '3000']);
 */
final class App
{
    private ?string $ver = null;

    /** @var list<array{name:string, help:string, argType:ArgType, required:bool}> */
    private array $positionals = [];

    /** @var list<array{name:string, help:string, short:?string}> */
    private array $flags = [];

    /** @var list<array{name:string, help:string, argType:ArgType, short:?string, default:?string, envVar:?string}> */
    private array $options = [];

    /** @var array<string, App> */
    private array $subcommands = [];

    public function __construct(
        private readonly string $name,
        private readonly string $description,
    ) {}

    public function version(string $v): self
    {
        $this->ver = $v;
        return $this;
    }

    public function positional(
        string  $name,
        string  $help,
        ArgType $argType,
        bool    $required = false,
    ): self {
        $this->positionals[] = [
            'name' => $name, 'help' => $help,
            'argType' => $argType, 'required' => $required,
        ];
        return $this;
    }

    public function flag(string $name, string $help, ?string $short = null): self
    {
        $this->flags[] = ['name' => $name, 'help' => $help, 'short' => $short];
        return $this;
    }

    public function option(
        string  $name,
        string  $help,
        ArgType $argType,
        ?string $short   = null,
        ?string $default = null,
        ?string $envVar  = null,
    ): self {
        $this->options[] = [
            'name' => $name, 'help' => $help, 'argType' => $argType,
            'short' => $short, 'default' => $default, 'envVar' => $envVar,
        ];
        return $this;
    }

    public function sub(App $sub): self
    {
        $this->subcommands[$sub->name] = $sub;
        return $this;
    }

    // ── Help ──

    public function help(): string
    {
        $out = $this->name;
        if ($this->ver !== null) {
            $out .= ' ' . $this->ver;
        }
        $out .= "\n{$this->description}\n\n";

        $out .= "USAGE:\n    {$this->name}";
        if ($this->subcommands) {
            $out .= ' <COMMAND>';
        }
        if ($this->options || $this->flags) {
            $out .= ' [OPTIONS]';
        }
        foreach ($this->positionals as $p) {
            $n = strtoupper($p['name']);
            $out .= $p['required'] ? " <{$n}>" : " [{$n}]";
        }
        $out .= "\n\n";

        if ($this->positionals) {
            $out .= "ARGS:\n";
            foreach ($this->positionals as $p) {
                $n   = strtoupper($p['name']);
                $req = $p['required'] ? ' (required)' : '';
                $out .= "    <{$n}>    {$p['help']}{$req}\n";
            }
            $out .= "\n";
        }

        if ($this->subcommands) {
            $out .= "COMMANDS:\n";
            $names = array_keys($this->subcommands);
            sort($names);
            foreach ($names as $n) {
                $desc = $this->subcommands[$n]->description;
                $out .= sprintf("    %-16s%s\n", $n, $desc);
            }
            $out .= "\n";
        }

        if ($this->flags || $this->options) {
            $out .= "OPTIONS:\n";
            foreach ($this->flags as $f) {
                $s = $f['short'] ? "-{$f['short']}, " : '    ';
                $out .= sprintf("    %s--%-16s%s\n", $s, $f['name'], $f['help']);
            }
            foreach ($this->options as $o) {
                $s = $o['short'] ? "-{$o['short']}, " : '    ';
                $d = $o['default'] !== null && $o['default'] !== '' ? " [default: {$o['default']}]" : '';
                $e = $o['envVar'] !== null && $o['envVar'] !== '' ? " [env: {$o['envVar']}]" : '';
                $out .= sprintf("    %s--%-16s%s%s%s\n", $s, $o['name'], $o['help'], $d, $e);
            }
            $out .= "        --help            Show this help message\n";
        }

        return $out;
    }

    // ── Parse ──

    /**
     * Parse args (first element = program name, skipped).
     *
     * @param list<string> $args
     */
    public function parse(array $args): Matches
    {
        return $this->parseSlice(array_slice($args, 1));
    }

    /**
     * Parse from $_SERVER['argv'].
     */
    public function parseEnv(): Matches
    {
        return $this->parse($_SERVER['argv'] ?? []);
    }

    // ── Internal ──

    /**
     * @param list<string> $args
     */
    private function parseSlice(array $args): Matches
    {
        $matches = new Matches();
        $posIdx  = 0;
        $i       = 0;
        $afterDD = false;
        $count   = count($args);

        while ($i < $count) {
            $arg = $args[$i];

            if ($afterDD) {
                $matches->addRest($arg);
                $i++;
                continue;
            }

            if ($arg === '--') {
                $afterDD = true;
                $i++;
                continue;
            }

            // --name=value or --name value
            if (str_starts_with($arg, '--')) {
                $rest = substr($arg, 2);
                if ($rest === 'help') {
                    echo $this->help();
                    exit(0);
                }

                $eqPos = strpos($rest, '=');
                if ($eqPos !== false) {
                    $optName   = substr($rest, 0, $eqPos);
                    $inlineVal = substr($rest, $eqPos + 1);
                } else {
                    $optName   = $rest;
                    $inlineVal = null;
                }

                // Flag?
                $flagDef = $this->findFlag($optName);
                if ($flagDef !== null) {
                    $matches->setFlag($optName);
                    $i++;
                    continue;
                }

                // Option?
                $optDef = $this->findOpt($optName);
                if ($optDef !== null) {
                    if ($inlineVal !== null) {
                        $valStr = $inlineVal;
                    } else {
                        $i++;
                        if ($i >= $count) {
                            throw new ParseError('missing_value', "missing value for: --{$optName}");
                        }
                        $valStr = $args[$i];
                    }
                    $matches->setValue($optDef['name'], self::parseValue($optDef['name'], $valStr, $optDef['argType']));
                    $i++;
                    continue;
                }

                throw new ParseError('unknown_arg', "unknown argument: --{$optName}");
            }

            // Short: -v, -p value, -vn
            if (str_starts_with($arg, '-') && strlen($arg) > 1) {
                $chars = mb_str_split(substr($arg, 1));
                $ci    = 0;
                $cLen  = count($chars);

                while ($ci < $cLen) {
                    $ch = $chars[$ci];

                    $flagDef = $this->findFlagShort($ch);
                    if ($flagDef !== null) {
                        $matches->setFlag($flagDef['name']);
                        $ci++;
                        continue;
                    }

                    $optDef = $this->findOptShort($ch);
                    if ($optDef !== null) {
                        if ($ci + 1 < $cLen) {
                            $valStr = implode('', array_slice($chars, $ci + 1));
                        } else {
                            $i++;
                            if ($i >= $count) {
                                throw new ParseError('missing_value', "missing value for: {$optDef['name']}");
                            }
                            $valStr = $args[$i];
                        }
                        $matches->setValue($optDef['name'], self::parseValue($optDef['name'], $valStr, $optDef['argType']));
                        // consumed rest of chars — break to next arg
                        break;
                    }

                    throw new ParseError('unknown_arg', "unknown argument: -{$ch}");
                }

                $i++;
                continue;
            }

            // Subcommand?
            if ($posIdx === 0 && isset($this->subcommands[$arg])) {
                $sub       = $this->subcommands[$arg];
                $subArgs   = array_slice($args, $i + 1);
                $subM      = $sub->parseSlice($subArgs);
                $matches->setSubcommand($arg, $subM);
                return $matches;
            }

            // Positional
            if ($posIdx < count($this->positionals)) {
                $p = $this->positionals[$posIdx];
                $matches->setValue($p['name'], self::parseValue($p['name'], $arg, $p['argType']));
                $posIdx++;
            } else {
                $matches->addRest($arg);
            }

            $i++;
        }

        // Defaults and env vars
        foreach ($this->options as $o) {
            if (!$matches->hasValue($o['name'])) {
                if ($o['envVar'] !== null && $o['envVar'] !== '') {
                    $envVal = getenv($o['envVar']);
                    if ($envVal !== false) {
                        try {
                            $matches->setValue($o['name'], self::parseValue($o['name'], $envVal, $o['argType']));
                            continue;
                        } catch (ParseError) {
                            // fall through to default
                        }
                    }
                }
                if ($o['default'] !== null && $o['default'] !== '') {
                    try {
                        $matches->setValue($o['name'], self::parseValue($o['name'], $o['default'], $o['argType']));
                    } catch (ParseError) {
                        // ignore bad default
                    }
                }
            }
        }

        // Required check
        foreach ($this->positionals as $p) {
            if ($p['required'] && !$matches->hasValue($p['name'])) {
                throw new ParseError('missing_required', "missing required argument: {$p['name']}");
            }
        }

        return $matches;
    }

    // ── Lookup helpers ──

    /** @return array{name:string, help:string, short:?string}|null */
    private function findFlag(string $name): ?array
    {
        foreach ($this->flags as $f) {
            if ($f['name'] === $name) return $f;
        }
        return null;
    }

    /** @return array{name:string, help:string, short:?string}|null */
    private function findFlagShort(string $ch): ?array
    {
        foreach ($this->flags as $f) {
            if ($f['short'] === $ch) return $f;
        }
        return null;
    }

    /** @return array{name:string, help:string, argType:ArgType, short:?string, default:?string, envVar:?string}|null */
    private function findOpt(string $name): ?array
    {
        foreach ($this->options as $o) {
            if ($o['name'] === $name) return $o;
        }
        return null;
    }

    /** @return array{name:string, help:string, argType:ArgType, short:?string, default:?string, envVar:?string}|null */
    private function findOptShort(string $ch): ?array
    {
        foreach ($this->options as $o) {
            if ($o['short'] === $ch) return $o;
        }
        return null;
    }

    // ── Value parsing ──

    private static function parseValue(string $name, string $raw, ArgType $type): Value
    {
        return match ($type) {
            ArgType::STR => Value::str($raw),
            ArgType::INT => self::parseInt($name, $raw),
            ArgType::FLOAT => self::parseFloat($name, $raw),
            ArgType::BOOL => self::parseBool($name, $raw),
        };
    }

    private static function parseInt(string $name, string $raw): Value
    {
        if (!preg_match('/^-?\d+$/', $raw)) {
            throw new ParseError('invalid_type', "invalid value '{$raw}' for {$name}");
        }
        return Value::int((int) $raw);
    }

    private static function parseFloat(string $name, string $raw): Value
    {
        if (!is_numeric($raw)) {
            throw new ParseError('invalid_type', "invalid value '{$raw}' for {$name}");
        }
        return Value::float((float) $raw);
    }

    private static function parseBool(string $name, string $raw): Value
    {
        return match ($raw) {
            'true', '1', 'yes', 'on' => Value::bool(true),
            'false', '0', 'no', 'off' => Value::bool(false),
            default => throw new ParseError('invalid_type', "invalid value '{$raw}' for {$name}"),
        };
    }
}
