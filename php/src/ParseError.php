<?php

declare(strict_types=1);

namespace LombokCLIParse;

/**
 * Represents an argument parsing error.
 */
class ParseError extends \RuntimeException
{
    public function __construct(
        public readonly string $kind,
        string $message,
    ) {
        parent::__construct($message);
    }
}
