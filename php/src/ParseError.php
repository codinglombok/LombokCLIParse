<?php

declare(strict_types=1);

namespace LombokCLIParse;

/**
 * Thrown when parsing stops. HELP and VERSION are not failures: `text` holds
 * what to print (use App::run() to handle them). The message is
 * "CODE: message" (SPEC section 6).
 */
class ParseError extends \RuntimeException
{
    public function __construct(
        public readonly string $errorCode,
        public readonly string $arg = '',
        public readonly ?string $value = null,
        public readonly ?string $reason = null,
        public readonly ?string $text = null,
    ) {
        parent::__construct($text ?? $errorCode . ': ' . self::describe($errorCode, $arg, $value, $reason));
    }

    private static function describe(string $code, string $arg, ?string $value, ?string $reason): string
    {
        return match ($code) {
            'UNKNOWN_ARGUMENT' => "unknown argument '$arg'",
            'MISSING_VALUE' => "missing value for '$arg'",
            'INVALID_VALUE' => "invalid value '$value' for '$arg'",
            'MISSING_REQUIRED' => "missing required argument '$arg'",
            'UNEXPECTED_ARGUMENT' => "unexpected argument '$arg'",
            'UNKNOWN_SUBCOMMAND' => "unknown subcommand '$arg'",
            'FLAG_TAKES_NO_VALUE' => "flag '$arg' does not take a value",
            'INVALID_DEFINITION' => "$reason: '$arg'",
        };
    }

    /** True for HELP and VERSION, which should exit with status 0. */
    public function isInfo(): bool
    {
        return $this->errorCode === 'HELP' || $this->errorCode === 'VERSION';
    }
}
