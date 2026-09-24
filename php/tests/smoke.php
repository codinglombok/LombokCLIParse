<?php

declare(strict_types=1);

require_once __DIR__ . '/../src/ArgType.php';
require_once __DIR__ . '/../src/ParseError.php';
require_once __DIR__ . '/../src/Value.php';
require_once __DIR__ . '/../src/Matches.php';
require_once __DIR__ . '/../src/App.php';

use LombokCLIParse\App;
use LombokCLIParse\ArgType;
use LombokCLIParse\ParseError;

$passed = 0;
$failed = 0;

function assert_eq(mixed $a, mixed $b, string $name): void
{
    global $passed, $failed;
    if ($a === $b) {
        $passed++;
    } else {
        $failed++;
        $aStr = var_export($a, true);
        $bStr = var_export($b, true);
        echo "FAIL: {$name} — expected {$bStr}, got {$aStr}\n";
    }
}

function assert_true(bool $cond, string $name): void
{
    global $passed, $failed;
    if ($cond) {
        $passed++;
    } else {
        $failed++;
        echo "FAIL: {$name}\n";
    }
}

function test_app(): App
{
    return (new App('testapp', 'A test application'))
        ->version('0.1.0')
        ->positional('input', 'Input file', ArgType::STR, required: true)
        ->positional('output', 'Output file', ArgType::STR, required: false)
        ->flag('verbose', 'Verbose output', short: 'v')
        ->flag('dry-run', 'Dry run mode', short: 'n')
        ->option('port', 'Port number', ArgType::INT, short: 'p', default: '8080')
        ->option('host', 'Hostname', ArgType::STR, short: 'h', default: 'localhost')
        ->option('config', 'Config path', ArgType::STR, short: 'c', envVar: 'TEST_CONFIG')
        ->option('rate', 'Rate limit', ArgType::FLOAT, short: 'r');
}

// Basic positional
$m = test_app()->parse(['app', 'input.txt']);
assert_eq($m->getStr('input'), 'input.txt', 'basic positional');

// Two positionals
$m = test_app()->parse(['app', 'in.txt', 'out.txt']);
assert_eq($m->getStr('input'), 'in.txt', 'two positionals input');
assert_eq($m->getStr('output'), 'out.txt', 'two positionals output');

// Missing required
try {
    test_app()->parse(['app']);
    assert_true(false, 'missing required should throw');
} catch (ParseError $e) {
    assert_eq($e->kind, 'missing_required', 'missing required kind');
}

// Flags long
$m = test_app()->parse(['app', 'f.txt', '--verbose']);
assert_true($m->getBool('verbose'), 'flag long verbose');
assert_true(!$m->getBool('dry-run'), 'flag long dry-run off');

// Flags short
$m = test_app()->parse(['app', 'f.txt', '-v', '-n']);
assert_true($m->getBool('verbose'), 'flag short -v');
assert_true($m->getBool('dry-run'), 'flag short -n');

// Combined short flags
$m = test_app()->parse(['app', 'f.txt', '-vn']);
assert_true($m->getBool('verbose'), 'combined -vn verbose');
assert_true($m->getBool('dry-run'), 'combined -vn dry-run');

// Option long
$m = test_app()->parse(['app', 'f.txt', '--port', '3000']);
assert_eq($m->getInt('port'), 3000, 'option long port');

// Option long equals
$m = test_app()->parse(['app', 'f.txt', '--port=9090']);
assert_eq($m->getInt('port'), 9090, 'option long equals');

// Option short
$m = test_app()->parse(['app', 'f.txt', '-p', '4000']);
assert_eq($m->getInt('port'), 4000, 'option short');

// Defaults
$m = test_app()->parse(['app', 'f.txt']);
assert_eq($m->getInt('port'), 8080, 'default port');
assert_eq($m->getStr('host'), 'localhost', 'default host');

// Float option
$m = test_app()->parse(['app', 'f.txt', '--rate', '1.5']);
assert_eq($m->getFloat('rate'), 1.5, 'float option');

// Invalid type
try {
    test_app()->parse(['app', 'f.txt', '--port', 'abc']);
    assert_true(false, 'invalid type should throw');
} catch (ParseError $e) {
    assert_eq($e->kind, 'invalid_type', 'invalid type kind');
}

// Unknown flag
try {
    test_app()->parse(['app', 'f.txt', '--unknown']);
    assert_true(false, 'unknown flag should throw');
} catch (ParseError $e) {
    assert_eq($e->kind, 'unknown_arg', 'unknown flag kind');
}

// Double dash
$m = test_app()->parse(['app', 'f.txt', '--', '--not-a-flag', 'extra']);
assert_eq(count($m->rest()), 2, 'double dash rest count');
assert_eq($m->rest()[0], '--not-a-flag', 'double dash rest 0');
assert_eq($m->rest()[1], 'extra', 'double dash rest 1');

// Subcommand
$app = (new App('cli', 'CLI tool'))
    ->flag('verbose', 'Verbose', short: 'v')
    ->sub(
        (new App('ingest', 'Ingest data'))
            ->positional('path', 'Data path', ArgType::STR, required: true)
            ->flag('force', 'Force overwrite', short: 'f')
    )
    ->sub(
        (new App('query', 'Query data'))
            ->positional('text', 'Query text', ArgType::STR, required: true)
            ->option('limit', 'Result limit', ArgType::INT, short: 'l', default: '10')
    );

$m = $app->parse(['cli', 'ingest', 'data/', '--force']);
$sub = $m->subcommand();
assert_eq($sub[0], 'ingest', 'subcommand name');
assert_eq($sub[1]->getStr('path'), 'data/', 'subcommand path');
assert_true($sub[1]->getBool('force'), 'subcommand flag');

// Subcommand query
$app2 = (new App('cli', 'CLI tool'))
    ->sub(
        (new App('query', 'Query data'))
            ->positional('text', 'Query text', ArgType::STR, required: true)
            ->option('limit', 'Result limit', ArgType::INT, short: 'l', default: '10')
    );
$m = $app2->parse(['cli', 'query', 'hello world', '-l', '5']);
$sub = $m->subcommand();
assert_eq($sub[0], 'query', 'subcommand query name');
assert_eq($sub[1]->getStr('text'), 'hello world', 'subcommand query text');
assert_eq($sub[1]->getInt('limit'), 5, 'subcommand query limit');

// Help text
$h = test_app()->help();
assert_true(str_contains($h, 'testapp'), 'help has name');
assert_true(str_contains($h, 'A test application'), 'help has desc');
assert_true(str_contains($h, '--verbose'), 'help has verbose');
assert_true(str_contains($h, '-v'), 'help has -v');
assert_true(str_contains($h, '[default: 8080]'), 'help has default');
assert_true(str_contains($h, '[env: TEST_CONFIG]'), 'help has env');
assert_true(str_contains($h, '<INPUT>'), 'help has INPUT');

// Env var fallback
putenv('TEST_CONFIG=/etc/test.toml');
$m = test_app()->parse(['app', 'f.txt']);
assert_eq($m->getStr('config'), '/etc/test.toml', 'env var fallback');
putenv('TEST_CONFIG');

// Mixed flags and positionals
$m = test_app()->parse(['app', '-v', 'input.txt', '--port', '3000', 'output.txt', '-n']);
assert_true($m->getBool('verbose'), 'mixed verbose');
assert_true($m->getBool('dry-run'), 'mixed dry-run');
assert_eq($m->getStr('input'), 'input.txt', 'mixed input');
assert_eq($m->getStr('output'), 'output.txt', 'mixed output');
assert_eq($m->getInt('port'), 3000, 'mixed port');

echo "\n{$passed} passed, {$failed} failed\n";
exit($failed > 0 ? 1 : 0);
