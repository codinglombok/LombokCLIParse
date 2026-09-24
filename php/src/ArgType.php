<?php

declare(strict_types=1);

namespace LombokCLIParse;

/**
 * Argument value types.
 */
enum ArgType: string
{
    case STR   = 'str';
    case INT   = 'int';
    case BOOL  = 'bool';
    case FLOAT = 'float';
}
