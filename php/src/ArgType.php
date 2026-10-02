<?php

declare(strict_types=1);

namespace LombokCLIParse;

/**
 * Type of a positional argument or option (SPEC section 3).
 */
enum ArgType: string
{
    case STR   = 'string';
    case INT   = 'int';
    case BOOL  = 'bool';
    case FLOAT = 'float';
}
