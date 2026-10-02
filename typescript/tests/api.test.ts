import { test } from 'node:test';
import assert from 'node:assert/strict';
import { App, ArgType, ParseError, parseValue } from '../src/index.js';

const app = () =>
    new App('tool', 'A tool')
        .version('1.0')
        .positional('input', 'Input', ArgType.Str, true)
        .flag('verbose', 'Verbose', 'v')
        .option('level', 'Level', ArgType.Int, 'l', '3', 'TOOL_LEVEL')
        .option('ratio', 'Ratio', ArgType.Float)
        .option('color', 'Colour', ArgType.Bool);

test('getters', () => {
    const m = app().parseWithEnv(['in', '-v', '--ratio', '0.5', '--color', 'on']);
    assert.equal(m.getStr('input'), 'in');
    assert.equal(m.getInt('level'), 3);
    assert.equal(m.getFloat('ratio'), 0.5);
    assert.equal(m.getFloat('level'), undefined);
    assert.equal(m.getInt('ratio'), undefined);
    assert.equal(m.getStr('level'), undefined);
    assert.equal(m.getBool('verbose'), true);
    assert.equal(m.getBool('color'), true);
    assert.equal(m.getBool('missing'), false);
    assert.equal(m.get('level'), 3);
    assert.equal(m.subcommand(), undefined);
    assert.deepEqual(m.rest(), []);
});

test('environment: function, record and process.env', () => {
    assert.equal(app().parseWithEnv(['x'], n => (n === 'TOOL_LEVEL' ? '9' : undefined)).getInt('level'), 9);
    assert.equal(app().parseWithEnv(['x'], { TOOL_LEVEL: '8' }).getInt('level'), 8);
    assert.equal(app().parseWithEnv(['x'], Object.create({ TOOL_LEVEL: '7' })).getInt('level'), 3, 'inherited keys are ignored');
    process.env.LOMBOKCLIPARSE_TEST = '5';
    const a = new App('t').option('n', '', ArgType.Int, undefined, undefined, 'LOMBOKCLIPARSE_TEST');
    assert.equal(a.parse(['t']).getInt('n'), 5);
});

test('help, version and errors', () => {
    assert.throws(() => app().parseWithEnv(['--help']), (e: unknown) => e instanceof ParseError && e.isInfo && e.code === 'HELP' && e.text === app().help() && e.message === e.text);
    assert.throws(() => app().parseWithEnv(['--version']), (e: unknown) => e instanceof ParseError && e.text === 'tool 1.0\n');
    assert.throws(
        () => app().parseWithEnv(['x', '-l', 'z']),
        (e: unknown) => e instanceof ParseError && !e.isInfo && e.value === 'z' && e.message === "INVALID_VALUE: invalid value 'z' for '-l'" && e.name === 'ParseError',
    );
    assert.throws(() => new App('d').sub(new App('bad name')).validate(), /INVALID_DEFINITION: invalid name: 'bad name'/);
    assert.doesNotThrow(() => new App('d').subcommand(new App('s')).validate());
});

test('parseValue', () => {
    assert.equal(parseValue(ArgType.Int, '-0'), 0);
    assert.ok(Object.is(parseValue(ArgType.Int, '-0'), 0));
    assert.equal(parseValue(ArgType.Int, '00000000000000000000000001'), 1);
    assert.equal(parseValue(ArgType.Int, '99999999999999999'), undefined);
    assert.equal(parseValue(ArgType.Float, '1e+'), undefined);
    assert.equal(parseValue(ArgType.Bool, 'ÿes'), undefined);
});
