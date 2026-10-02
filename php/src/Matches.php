<?php

declare(strict_types=1);

namespace LombokCLIParse;

/**
 * The result of a successful parse.
 */
final class Matches
{
    /** @var array<string, Value> */
    private array $values = [];
    /** @var array<string, true> */
    private array $flags = [];
    private ?string $subName = null;
    private ?Matches $sub = null;
    /** @var list<string> */
    private array $rest = [];

    /** @internal */
    public function setValue(string $name, Value $v): void
    {
        $this->values[$name] = $v;
    }

    /** @internal */
    public function setFlag(string $name): void
    {
        $this->flags[$name] = true;
    }

    /** @internal */
    public function setSubcommand(string $name, Matches $m): void
    {
        $this->subName = $name;
        $this->sub = $m;
    }

    /** @internal */
    public function addRest(string $arg): void
    {
        $this->rest[] = $arg;
    }

    public function hasValue(string $name): bool
    {
        return isset($this->values[$name]);
    }

    public function getStr(string $name): ?string
    {
        $v = $this->values[$name] ?? null;
        return $v?->type === ArgType::STR ? $v->str : null;
    }

    public function getInt(string $name): ?int
    {
        $v = $this->values[$name] ?? null;
        return $v?->type === ArgType::INT ? $v->int : null;
    }

    public function getFloat(string $name): ?float
    {
        $v = $this->values[$name] ?? null;
        return $v?->type === ArgType::FLOAT ? $v->float : null;
    }

    /** True when the flag was given or a bool option is true. */
    public function getBool(string $name): bool
    {
        $v = $this->values[$name] ?? null;
        return isset($this->flags[$name]) || ($v?->type === ArgType::BOOL && $v->bool);
    }

    public function get(string $name): ?Value
    {
        return $this->values[$name] ?? null;
    }

    /** @return array<string, Value> sorted by name */
    public function values(): array
    {
        $v = $this->values;
        ksort($v, SORT_STRING);
        return $v;
    }

    /** @return list<string> names of the flags given, sorted */
    public function flags(): array
    {
        $f = array_map('strval', array_keys($this->flags));
        sort($f, SORT_STRING);
        return $f;
    }

    /** @return array{0: string, 1: Matches}|null */
    public function subcommand(): ?array
    {
        return $this->sub === null ? null : [$this->subName, $this->sub];
    }

    /** @return list<string> tokens after "--" that did not fill a positional argument */
    public function rest(): array
    {
        return $this->rest;
    }
}
