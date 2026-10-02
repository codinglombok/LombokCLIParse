<?php

declare(strict_types=1);

require_once __DIR__ . '/bootstrap.php';

use LombokCLIParse\App;
use LombokCLIParse\ArgType;
use LombokCLIParse\ParseError;

$app = static fn (): App => (new App('tool', 'A tool'))->version('1.0')
    ->positional('input', 'Input', ArgType::STR, true)
    ->flag('verbose', 'Verbose', 'v')
    ->option('level', 'Level', ArgType::INT, 'l', '3', 'TOOL_LEVEL')
    ->option('ratio', 'Ratio', ArgType::FLOAT)
    ->option('color', 'Colour', ArgType::BOOL);

$m = $app()->parseWithEnv(['in', '-v', '--ratio', '0.5', '--color', 'on']);
check($m->getStr('input') === 'in', 'getStr');
check($m->getInt('level') === 3, 'getInt');
check($m->getFloat('ratio') === 0.5, 'getFloat');
check($m->getFloat('level') === null && $m->getInt('ratio') === null && $m->getStr('level') === null, 'typed getters');
check($m->getBool('verbose') && $m->getBool('color') && !$m->getBool('missing'), 'getBool');
check($m->get('level')?->int === 3 && $m->get('missing') === null, 'get');
check($m->subcommand() === null && $m->rest() === [], 'sub/rest');

check($app()->parseWithEnv(['x'], static fn (string $k): ?string => $k === 'TOOL_LEVEL' ? '9' : null)->getInt('level') === 9, 'env callable');
check($app()->parseWithEnv(['x'], ['TOOL_LEVEL' => '8'])->getInt('level') === 8, 'env array');
putenv('LOMBOKCLIPARSE_TEST=5');
$t = (new App('t'))->option('n', '', ArgType::INT, null, null, 'LOMBOKCLIPARSE_TEST');
check($t->parse(['t'])->getInt('n') === 5, 'getenv');
$_SERVER['argv'] = ['t'];
check($t->parseEnv()->getInt('n') === 5, 'parseEnv');
check($t->run()->getInt('n') === 5, 'run without help');

try {
    $app()->parseWithEnv(['--help']);
    check(false, 'help');
} catch (ParseError $e) {
    check($e->isInfo() && $e->errorCode === 'HELP' && $e->text === $app()->help() && $e->getMessage() === $e->text, 'help text');
}
throwsCode(static fn () => $app()->parseWithEnv(['x', '-l', 'z']), 'INVALID_VALUE', 'invalid value');
try {
    $app()->parseWithEnv(['x', '-l', 'z']);
} catch (ParseError $e) {
    check(!$e->isInfo() && $e->value === 'z' && $e->getMessage() === "INVALID_VALUE: invalid value 'z' for '-l'", 'message');
}
throwsCode(static fn () => (new App('d'))->sub(new App('bad name'))->validate(), 'INVALID_DEFINITION', 'sub name');
throwsCode(static fn () => (new App('d'))->flag('a', '', 'é')->validate(), 'INVALID_DEFINITION', 'non-ASCII short');

check(App::parseValue(ArgType::INT, '1_000') === null, 'int underscore');
check(App::parseValue(ArgType::INT, '99999999999999999') === null, 'int too long');
check(App::parseValue(ArgType::INT, '-0')?->int === 0, 'minus zero');
check(App::parseValue(ArgType::FLOAT, 'inf') === null, 'inf');
check(App::parseValue(ArgType::BOOL, 'ÿes') === null, 'non-ASCII bool');

finish('api');
