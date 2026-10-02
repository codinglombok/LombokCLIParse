// Runs the shared vectors (vectors/lombokcliparse-vectors-v1.json).
import { test } from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { App, ArgType, Matches, ParseError } from '../src/index.js';

interface ArgDef { kind?: string; name: string; help: string; type?: string; required?: boolean; short?: string | null; default?: string | null; env?: string | null }
interface AppDef { name: string; description: string; version: string | null; positionals: ArgDef[]; args: ArgDef[]; subcommands: AppDef[] }
interface Case { id: string; app: AppDef; argv: string[]; env: Record<string, string>; expected: unknown }

const path = fileURLToPath(new URL('../../../vectors/lombokcliparse-vectors-v1.json', import.meta.url));
const doc = JSON.parse(readFileSync(path, 'utf8')) as { cases: Case[] };

const view = new DataView(new ArrayBuffer(8));
function bits(x: number): string {
    view.setFloat64(0, x);
    return '0x' + view.getBigUint64(0).toString(16).padStart(16, '0');
}

const opt = (v: string | null | undefined): string | undefined => (v === null ? undefined : v);

function build(d: AppDef): App {
    const app = new App(d.name, d.description);
    if (d.version !== null) app.version(d.version);
    for (const p of d.positionals) app.positional(p.name, p.help, p.type as ArgType, p.required);
    for (const a of d.args) {
        if (a.kind === 'flag') app.flag(a.name, a.help, opt(a.short));
        else app.option(a.name, a.help, a.type as ArgType, opt(a.short), opt(a.default), opt(a.env));
    }
    for (const s of d.subcommands) app.subcommand(build(s));
    return app;
}

function encode(m: Matches): unknown {
    const values: Record<string, unknown> = {};
    for (const [k, v] of m.values()) {
        const t = m.typeOf(k);
        values[k] = t === ArgType.Int ? { int: String(v) } : t === ArgType.Float ? { float: bits(v as number) } : t === ArgType.Bool ? { bool: v } : { str: v };
    }
    const sub = m.subcommand();
    return { values, flags: m.flags(), rest: m.rest(), subcommand: sub ? { name: sub.name, matches: encode(sub.matches) } : null };
}

function run(c: Case): unknown {
    try {
        return { matches: encode(build(c.app).parseWithEnv(c.argv, c.env)) };
    } catch (e) {
        if (!(e instanceof ParseError)) throw e;
        if (e.code === 'HELP') return { help: e.text };
        if (e.code === 'VERSION') return { version: e.text };
        const err: Record<string, string> = { code: e.code, arg: e.arg, message: e.message };
        if (e.value !== undefined) err.value = e.value;
        return { error: err };
    }
}

test('vector file has at least 100 cases', () => {
    assert.ok(doc.cases.length >= 100);
});

for (const c of doc.cases) {
    test(`vector ${c.id}`, () => {
        assert.deepStrictEqual(run(c), c.expected);
    });
}
