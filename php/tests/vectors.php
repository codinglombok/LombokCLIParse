<?php

declare(strict_types=1);

// Runs the shared vectors (vectors/lombokcliparse-vectors-v1.json).

require_once __DIR__ . '/bootstrap.php';

use LombokCLIParse\App;
use LombokCLIParse\ArgType;
use LombokCLIParse\Matches;
use LombokCLIParse\ParseError;

$doc = json_decode((string) file_get_contents(__DIR__ . '/../../vectors/lombokcliparse-vectors-v1.json'), true, 512, JSON_THROW_ON_ERROR);

function buildApp(array $d): App
{
    $app = new App($d['name'], $d['description']);
    if ($d['version'] !== null) {
        $app->version($d['version']);
    }
    foreach ($d['positionals'] as $p) {
        $app->positional($p['name'], $p['help'], ArgType::from($p['type']), $p['required']);
    }
    foreach ($d['args'] as $a) {
        if ($a['kind'] === 'flag') {
            $app->flag($a['name'], $a['help'], $a['short']);
        } else {
            $app->option($a['name'], $a['help'], ArgType::from($a['type']), $a['short'], $a['default'], $a['env']);
        }
    }
    foreach ($d['subcommands'] as $s) {
        $app->subcommand(buildApp($s));
    }
    return $app;
}

function encodeMatches(Matches $m): array
{
    $values = [];
    foreach ($m->values() as $k => $v) {
        $values[(string) $k] = match ($v->type) {
            ArgType::INT => ['int' => (string) $v->int],
            ArgType::FLOAT => ['float' => '0x' . bin2hex(pack('E', $v->float))],
            ArgType::BOOL => ['bool' => $v->bool],
            ArgType::STR => ['str' => $v->str],
        };
    }
    $sub = $m->subcommand();
    return [
        'values' => $values,
        'flags' => $m->flags(),
        'rest' => $m->rest(),
        'subcommand' => $sub === null ? null : ['name' => $sub[0], 'matches' => encodeMatches($sub[1])],
    ];
}

function runCase(array $c): array
{
    try {
        return ['matches' => encodeMatches(buildApp($c['app'])->parseWithEnv($c['argv'], $c['env']))];
    } catch (ParseError $e) {
        if ($e->errorCode === 'HELP') {
            return ['help' => $e->text];
        }
        if ($e->errorCode === 'VERSION') {
            return ['version' => $e->text];
        }
        $err = ['code' => $e->errorCode, 'arg' => $e->arg, 'message' => $e->getMessage()];
        if ($e->value !== null) {
            $err['value'] = $e->value;
        }
        return ['error' => $err];
    }
}

/** Sorts object keys recursively so both sides compare as canonical JSON. */
function canon(mixed $v): mixed
{
    if (is_array($v)) {
        $v = array_map('canon', $v);
        if (!array_is_list($v)) {
            ksort($v, SORT_STRING);
        }
    }
    return $v;
}

$flags = JSON_UNESCAPED_UNICODE | JSON_UNESCAPED_SLASHES;
check(count($doc['cases']) >= 100, 'at least 100 cases');
foreach ($doc['cases'] as $c) {
    $got = canon(runCase($c));
    $want = canon($c['expected']);
    check($got === $want, $c['id'] . ': got ' . json_encode($got, $flags) . ' want ' . json_encode($want, $flags));
}
finish('vectors');
