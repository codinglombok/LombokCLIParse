<?php

declare(strict_types=1);

namespace LombokCLIParse;

/**
 * Holds a parsed argument value.
 */
final class Value
{
    private function __construct(
        public readonly ArgType $type,
        public readonly string  $str   = '',
        public readonly int     $int   = 0,
        public readonly float   $float = 0.0,
        public readonly bool    $bool  = false,
    ) {}

    public static function str(string $v): self
    {
        return new self(ArgType::STR, str: $v);
    }

    public static function int(int $v): self
    {
        return new self(ArgType::INT, int: $v);
    }

    public static function float(float $v): self
    {
        return new self(ArgType::FLOAT, float: $v);
    }

    public static function bool(bool $v): self
    {
        return new self(ArgType::BOOL, bool: $v);
    }
}
