<?php

declare(strict_types=1);

namespace LombokCLIParse;

/**
 * Parsed argument results.
 */
final class Matches
{
    /** @var array<string, Value> */
    private array $values = [];

    /** @var array<string, bool> */
    private array $flags = [];

    /** @var array{string, Matches}|null */
    private ?array $subcommand = null;

    /** @var list<string> */
    private array $rest = [];

    public function setValue(string $name, Value $v): void
    {
        $this->values[$name] = $v;
    }

    public function setFlag(string $name): void
    {
        $this->flags[$name] = true;
    }

    public function setSubcommand(string $name, Matches $m): void
    {
        $this->subcommand = [$name, $m];
    }

    public function addRest(string $arg): void
    {
        $this->rest[] = $arg;
    }

    // ── Getters ──

    public function getStr(string $name): ?string
    {
        $v = $this->values[$name] ?? null;
        return ($v !== null && $v->type === ArgType::STR) ? $v->str : null;
    }

    public function getInt(string $name): ?int
    {
        $v = $this->values[$name] ?? null;
        return ($v !== null && $v->type === ArgType::INT) ? $v->int : null;
    }

    public function getFloat(string $name): ?float
    {
        $v = $this->values[$name] ?? null;
        return ($v !== null && $v->type === ArgType::FLOAT) ? $v->float : null;
    }

    public function getBool(string $name): bool
    {
        return $this->flags[$name] ?? false;
    }

    public function get(string $name): ?Value
    {
        return $this->values[$name] ?? null;
    }

    /**
     * @return array{string, Matches}|null
     */
    public function subcommand(): ?array
    {
        return $this->subcommand;
    }

    /**
     * @return list<string>
     */
    public function rest(): array
    {
        return $this->rest;
    }

    public function hasValue(string $name): bool
    {
        return isset($this->values[$name]);
    }
}
