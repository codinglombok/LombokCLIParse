import { App, ArgType, Matches, ParseError } from './index.js';

let pass = 0;
let fail = 0;

function assert(cond: boolean, name: string): void {
  if (cond) {
    pass++;
  } else {
    fail++;
    console.error(`FAIL: ${name}`);
  }
}

function assertEq<T>(a: T, b: T, name: string): void {
  if (a === b) {
    pass++;
  } else {
    fail++;
    console.error(`FAIL: ${name} — expected ${JSON.stringify(b)}, got ${JSON.stringify(a)}`);
  }
}

function testApp(): App {
  return new App('testapp', 'A test application')
    .version('0.1.0')
    .positional('input', 'Input file', ArgType.Str, true)
    .positional('output', 'Output file', ArgType.Str, false)
    .flag('verbose', 'Verbose output', 'v')
    .flag('dry-run', 'Dry run mode', 'n')
    .option('port', 'Port number', ArgType.Int, 'p', '8080')
    .option('host', 'Hostname', ArgType.Str, 'h', 'localhost')
    .option('config', 'Config path', ArgType.Str, 'c', undefined, 'TEST_CONFIG')
    .option('rate', 'Rate limit', ArgType.Float, 'r');
}

// --- Basic positional ---
{
  const m = testApp().parse(['app', 'input.txt']);
  assertEq(m.getStr('input'), 'input.txt', 'basic positional');
}

// --- Two positionals ---
{
  const m = testApp().parse(['app', 'in.txt', 'out.txt']);
  assertEq(m.getStr('input'), 'in.txt', 'two positionals input');
  assertEq(m.getStr('output'), 'out.txt', 'two positionals output');
}

// --- Missing required ---
{
  try {
    testApp().parse(['app']);
    assert(false, 'missing required should throw');
  } catch (e) {
    assert(e instanceof ParseError && e.kind === 'missing_required', 'missing required error');
  }
}

// --- Flags long ---
{
  const m = testApp().parse(['app', 'f.txt', '--verbose']);
  assert(m.getBool('verbose'), 'flag long verbose');
  assert(!m.getBool('dry-run'), 'flag long dry-run off');
}

// --- Flags short ---
{
  const m = testApp().parse(['app', 'f.txt', '-v', '-n']);
  assert(m.getBool('verbose'), 'flag short -v');
  assert(m.getBool('dry-run'), 'flag short -n');
}

// --- Combined short flags ---
{
  const m = testApp().parse(['app', 'f.txt', '-vn']);
  assert(m.getBool('verbose'), 'combined -vn verbose');
  assert(m.getBool('dry-run'), 'combined -vn dry-run');
}

// --- Option long ---
{
  const m = testApp().parse(['app', 'f.txt', '--port', '3000']);
  assertEq(m.getInt('port'), 3000, 'option long port');
}

// --- Option long equals ---
{
  const m = testApp().parse(['app', 'f.txt', '--port=9090']);
  assertEq(m.getInt('port'), 9090, 'option long equals');
}

// --- Option short ---
{
  const m = testApp().parse(['app', 'f.txt', '-p', '4000']);
  assertEq(m.getInt('port'), 4000, 'option short');
}

// --- Defaults ---
{
  const m = testApp().parse(['app', 'f.txt']);
  assertEq(m.getInt('port'), 8080, 'default port');
  assertEq(m.getStr('host'), 'localhost', 'default host');
}

// --- Float option ---
{
  const m = testApp().parse(['app', 'f.txt', '--rate', '1.5']);
  assertEq(m.getFloat('rate'), 1.5, 'float option');
}

// --- Invalid type ---
{
  try {
    testApp().parse(['app', 'f.txt', '--port', 'abc']);
    assert(false, 'invalid type should throw');
  } catch (e) {
    assert(e instanceof ParseError && e.kind === 'invalid_type', 'invalid type error');
  }
}

// --- Unknown flag ---
{
  try {
    testApp().parse(['app', 'f.txt', '--unknown']);
    assert(false, 'unknown flag should throw');
  } catch (e) {
    assert(e instanceof ParseError && e.kind === 'unknown_arg', 'unknown flag error');
  }
}

// --- Double dash ---
{
  const m = testApp().parse(['app', 'f.txt', '--', '--not-a-flag', 'extra']);
  const rest = m.rest();
  assertEq(rest.length, 2, 'double dash rest count');
  assertEq(rest[0], '--not-a-flag', 'double dash rest 0');
  assertEq(rest[1], 'extra', 'double dash rest 1');
}

// --- Subcommand ---
{
  const app = new App('cli', 'CLI tool')
    .flag('verbose', 'Verbose', 'v')
    .sub(
      new App('ingest', 'Ingest data')
        .positional('path', 'Data path', ArgType.Str, true)
        .flag('force', 'Force overwrite', 'f'),
    )
    .sub(
      new App('query', 'Query data')
        .positional('text', 'Query text', ArgType.Str, true)
        .option('limit', 'Result limit', ArgType.Int, 'l', '10'),
    );

  const m = app.parse(['cli', 'ingest', 'data/', '--force']);
  const sub = m.subcommand();
  assertEq(sub?.name, 'ingest', 'subcommand name');
  assertEq(sub?.matches.getStr('path'), 'data/', 'subcommand path');
  assert(sub?.matches.getBool('force') === true, 'subcommand flag');
}

// --- Subcommand query ---
{
  const app = new App('cli', 'CLI tool')
    .sub(
      new App('query', 'Query data')
        .positional('text', 'Query text', ArgType.Str, true)
        .option('limit', 'Result limit', ArgType.Int, 'l', '10'),
    );

  const m = app.parse(['cli', 'query', 'hello world', '-l', '5']);
  const sub = m.subcommand();
  assertEq(sub?.name, 'query', 'subcommand query name');
  assertEq(sub?.matches.getStr('text'), 'hello world', 'subcommand query text');
  assertEq(sub?.matches.getInt('limit'), 5, 'subcommand query limit');
}

// --- Help text ---
{
  const help = testApp().help();
  assert(help.includes('testapp'), 'help has name');
  assert(help.includes('A test application'), 'help has desc');
  assert(help.includes('--verbose'), 'help has verbose');
  assert(help.includes('-v'), 'help has -v');
  assert(help.includes('[default: 8080]'), 'help has default');
  assert(help.includes('[env: TEST_CONFIG]'), 'help has env');
  assert(help.includes('<INPUT>'), 'help has INPUT');
}

// --- Env var fallback ---
{
  process.env['TEST_CONFIG'] = '/etc/test.toml';
  const m = testApp().parse(['app', 'f.txt']);
  assertEq(m.getStr('config'), '/etc/test.toml', 'env var fallback');
  delete process.env['TEST_CONFIG'];
}

// --- Mixed flags and positionals ---
{
  const m = testApp().parse(['app', '-v', 'input.txt', '--port', '3000', 'output.txt', '-n']);
  assert(m.getBool('verbose'), 'mixed verbose');
  assert(m.getBool('dry-run'), 'mixed dry-run');
  assertEq(m.getStr('input'), 'input.txt', 'mixed input');
  assertEq(m.getStr('output'), 'output.txt', 'mixed output');
  assertEq(m.getInt('port'), 3000, 'mixed port');
}

console.log(`\n${pass} passed, ${fail} failed`);
process.exit(fail > 0 ? 1 : 0);
