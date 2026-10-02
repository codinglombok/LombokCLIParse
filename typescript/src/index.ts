/**
 * LombokCLIParse for TypeScript/JavaScript: positional arguments, flags, typed
 * options, subcommands, environment fallback and generated help. The same
 * input gives the same result, error message and help text in the Rust,
 * Python, Go and PHP ports (docs/SPEC_LombokCLIParse_v0.2.0.md).
 *
 * @example
 * ```ts
 * import { App, ArgType } from 'lombokcliparse';
 *
 * const app = new App('myapp', 'My application')
 *   .version('1.0.0')
 *   .positional('input', 'Input file', ArgType.Str, true)
 *   .flag('verbose', 'Verbose output', 'v')
 *   .option('port', 'Port', ArgType.Int, 'p', '8080');
 *
 * const m = app.parse(['myapp', 'data.txt', '-v', '-p', '3000']);
 * m.getInt('port'); // 3000
 * ```
 */

/** Type of a positional argument or option (SPEC section 3). */
export enum ArgType {
    Str = 'string',
    Int = 'int',
    Float = 'float',
    Bool = 'bool',
}

/** A parsed value. Ints are within ±(2^53 - 1), so they are exact numbers. */
export type Value = string | number | boolean;

/** Largest integer accepted by `ArgType.Int`. */
export const MAX_SAFE_INTEGER = Number.MAX_SAFE_INTEGER;

/** Error and info codes shared by every port (SPEC section 6). */
export type ParseErrorCode =
    | 'UNKNOWN_ARGUMENT'
    | 'MISSING_VALUE'
    | 'INVALID_VALUE'
    | 'MISSING_REQUIRED'
    | 'UNEXPECTED_ARGUMENT'
    | 'UNKNOWN_SUBCOMMAND'
    | 'FLAG_TAKES_NO_VALUE'
    | 'INVALID_DEFINITION'
    | 'HELP'
    | 'VERSION';

const MESSAGES: Record<string, (arg: string, value?: string, reason?: string) => string> = {
    UNKNOWN_ARGUMENT: a => `unknown argument '${a}'`,
    MISSING_VALUE: a => `missing value for '${a}'`,
    INVALID_VALUE: (a, v) => `invalid value '${v}' for '${a}'`,
    MISSING_REQUIRED: a => `missing required argument '${a}'`,
    UNEXPECTED_ARGUMENT: a => `unexpected argument '${a}'`,
    UNKNOWN_SUBCOMMAND: a => `unknown subcommand '${a}'`,
    FLAG_TAKES_NO_VALUE: a => `flag '${a}' does not take a value`,
    INVALID_DEFINITION: (a, _v, r) => `${r}: '${a}'`,
};

/**
 * Thrown when parsing stops. `HELP` and `VERSION` are not failures: `text`
 * holds what to print (use {@link App.run} to handle them).
 */
export class ParseError extends Error {
    readonly code: ParseErrorCode;
    /** The argument the error is about ('' for HELP and VERSION). */
    readonly arg: string;
    /** The rejected text for INVALID_VALUE. */
    readonly value?: string;
    /** The broken rule for INVALID_DEFINITION. */
    readonly reason?: string;
    /** Help or version text for HELP and VERSION. */
    readonly text?: string;

    constructor(code: ParseErrorCode, arg: string, opts: { value?: string; reason?: string; text?: string } = {}) {
        const msg = opts.text ?? `${code}: ${MESSAGES[code]!(arg, opts.value, opts.reason)}`;
        super(msg);
        this.name = 'ParseError';
        this.code = code;
        this.arg = arg;
        this.value = opts.value;
        this.reason = opts.reason;
        this.text = opts.text;
    }

    /** True for HELP and VERSION, which should exit with status 0. */
    get isInfo(): boolean {
        return this.code === 'HELP' || this.code === 'VERSION';
    }
}

const INT_RE = /^[+-]?[0-9]+$/;
const FLOAT_RE = /^[+-]?([0-9]+(\.[0-9]*)?|\.[0-9]+)([eE][+-]?[0-9]+)?$/;
const ASCII_RE = /^[\x00-\x7f]*$/;
const BOOLS: Record<string, boolean> = { true: true, '1': true, yes: true, on: true, false: false, '0': false, no: false, off: false };

/** Parses `raw` as `type`; `undefined` when the text is not valid for the type. */
export function parseValue(type: ArgType, raw: string): Value | undefined {
    switch (type) {
        case ArgType.Str:
            return raw;
        case ArgType.Int: {
            if (!INT_RE.test(raw)) return undefined;
            if (raw.replace(/^[+-]/, '').replace(/^0+/, '').length > 16) return undefined;
            const v = Number(raw);
            return Math.abs(v) <= MAX_SAFE_INTEGER ? v + 0 : undefined;
        }
        case ArgType.Float: {
            if (!FLOAT_RE.test(raw)) return undefined;
            const v = Number(raw);
            return Number.isFinite(v) ? v : undefined;
        }
        case ArgType.Bool:
            if (!ASCII_RE.test(raw)) return undefined;
            return BOOLS[raw.toLowerCase()];
    }
}

interface Positional {
    name: string;
    help: string;
    type: ArgType;
    required: boolean;
}

interface Named {
    kind: 'flag' | 'option';
    name: string;
    help: string;
    short?: string;
    type?: ArgType;
    default?: string;
    env?: string;
}

/** The result of a successful parse. */
export class Matches {
    /** @internal */ readonly _values = new Map<string, Value>();
    /** @internal */ readonly _flags = new Set<string>();
    /** @internal */ _sub?: { name: string; matches: Matches };
    /** @internal */ readonly _rest: string[] = [];

    /** A string value. */
    getStr(name: string): string | undefined {
        const v = this._values.get(name);
        return typeof v === 'string' ? v : undefined;
    }

    /** An int value (an `ArgType.Int` argument). */
    getInt(name: string): number | undefined {
        const v = this._values.get(name);
        return typeof v === 'number' && Number.isInteger(v) && this._types.get(name) === ArgType.Int ? v : undefined;
    }

    /** A float value (an `ArgType.Float` argument). */
    getFloat(name: string): number | undefined {
        const v = this._values.get(name);
        return typeof v === 'number' && this._types.get(name) === ArgType.Float ? v : undefined;
    }

    /** True when the flag was given or a bool option is true. */
    getBool(name: string): boolean {
        return this._flags.has(name) || this._values.get(name) === true;
    }

    /** Any value by name. */
    get(name: string): Value | undefined {
        return this._values.get(name);
    }

    /** The type of a stored value. */
    typeOf(name: string): ArgType | undefined {
        return this._types.get(name);
    }

    /** All values, sorted by name. */
    values(): [string, Value][] {
        return [...this._values.entries()].sort(([a], [b]) => (a < b ? -1 : a > b ? 1 : 0));
    }

    /** Names of the flags that were given, sorted. */
    flags(): string[] {
        return [...this._flags].sort();
    }

    /** The selected subcommand and its matches. */
    subcommand(): { name: string; matches: Matches } | undefined {
        return this._sub;
    }

    /** Tokens after `--` that did not fill a positional argument. */
    rest(): string[] {
        return this._rest;
    }

    /** @internal */ readonly _types = new Map<string, ArgType>();
}

const NAME_RE = /^[A-Za-z0-9][A-Za-z0-9_-]*$/;
const SHORT_RE = /^[A-Za-z]$/;
const PLACEHOLDER: Record<ArgType, string> = {
    [ArgType.Str]: '<VALUE>',
    [ArgType.Int]: '<INT>',
    [ArgType.Float]: '<FLOAT>',
    [ArgType.Bool]: '<BOOL>',
};

const cpLength = (s: string): number => [...s].length;
const joinParts = (parts: string[]): string => parts.filter(p => p !== '').join(' ');

function section(title: string, rows: [string, string][]): string {
    const width = Math.max(...rows.map(([l]) => cpLength(l)));
    let out = `${title}:\n`;
    for (const [left, help] of rows) {
        out += help ? `    ${left}${' '.repeat(width - cpLength(left) + 2)}${help}\n` : `    ${left}\n`;
    }
    return out;
}

function defErr(arg: string, reason: string): ParseError {
    return new ParseError('INVALID_DEFINITION', arg, { reason });
}

/** Looks up an environment variable; `undefined` when unset. */
export type EnvLookup = (name: string) => string | undefined;

/** A command-line application or subcommand definition (builder). */
export class App {
    private readonly _name: string;
    private readonly _description: string;
    private _version?: string;
    private readonly positionals: Positional[] = [];
    private readonly args: Named[] = [];
    private readonly subs: App[] = [];

    constructor(name: string, description = '') {
        this._name = name;
        this._description = description;
    }

    /** Sets the version; enables `--version`. */
    version(v: string): this {
        this._version = v;
        return this;
    }

    /** Adds a positional argument (filled in definition order). */
    positional(name: string, help: string, type: ArgType = ArgType.Str, required = false): this {
        this.positionals.push({ name, help, type, required });
        return this;
    }

    /** Adds a boolean flag, `--name` or `-c`. */
    flag(name: string, help: string, short?: string): this {
        this.args.push({ kind: 'flag', name, help, short });
        return this;
    }

    /** Adds an option taking a value; when absent, `env` and then `defaultValue` are used. */
    option(name: string, help: string, type: ArgType = ArgType.Str, short?: string, defaultValue?: string, env?: string): this {
        this.args.push({ kind: 'option', name, help, short, type, default: defaultValue, env });
        return this;
    }

    /** Adds a subcommand. An app with subcommands has no positional arguments. */
    subcommand(sub: App): this {
        this.subs.push(sub);
        return this;
    }

    /** Same as {@link App.subcommand} (0.1 name). */
    sub(sub: App): this {
        return this.subcommand(sub);
    }

    /** Checks the rules of SPEC section 2; throws INVALID_DEFINITION. */
    validate(): void {
        const reserved = (n: string): boolean => n === 'help' || (n === 'version' && this._version !== undefined);
        const names = new Set<string>();
        const shorts = new Set<string>();
        const entries: (Positional | Named)[] = [...this.positionals, ...this.args];
        for (const a of entries) {
            if (!NAME_RE.test(a.name)) throw defErr(a.name, 'invalid name');
            if (reserved(a.name)) throw defErr(a.name, 'reserved name');
            if (names.has(a.name)) throw defErr(a.name, 'duplicate name');
            names.add(a.name);
            if ('kind' in a) {
                if (a.short !== undefined) {
                    if (!SHORT_RE.test(a.short)) throw defErr(a.short, 'invalid short');
                    if (shorts.has(a.short)) throw defErr(a.short, 'duplicate short');
                    shorts.add(a.short);
                }
                if (a.kind === 'option' && a.default !== undefined && parseValue(a.type!, a.default) === undefined) {
                    throw defErr(a.name, 'invalid default');
                }
            }
        }
        let seenOptional = false;
        for (const p of this.positionals) {
            if (p.required && seenOptional) throw defErr(p.name, 'required after optional');
            if (!p.required) seenOptional = true;
        }
        if (this.subs.length > 0 && this.positionals.length > 0) throw defErr(this.subs[0]!._name, 'positionals with subcommands');
        const subNames = new Set<string>();
        for (const s of this.subs) {
            if (!NAME_RE.test(s._name)) throw defErr(s._name, 'invalid name');
            if (subNames.has(s._name)) throw defErr(s._name, 'duplicate name');
            subNames.add(s._name);
            s.validate();
        }
    }

    /** The help text (SPEC section 5) as shown for `--help`. */
    help(): string {
        return this.helpAt(this._name);
    }

    private helpAt(path: string): string {
        let out = this._name + (this._version !== undefined ? ` ${this._version}` : '') + '\n';
        if (this._description) out += `${this._description}\n`;
        out += `\nUSAGE:\n    ${path} [OPTIONS]`;
        if (this.subs.length > 0) out += ' <COMMAND>';
        for (const p of this.positionals) {
            const n = p.name.toUpperCase();
            out += p.required ? ` <${n}>` : ` [${n}]`;
        }
        out += '\n';
        if (this.positionals.length > 0) {
            out += '\n' + section('ARGS', this.positionals.map(p => [`<${p.name.toUpperCase()}>`, joinParts([p.help, p.required ? '(required)' : ''])]));
        }
        if (this.subs.length > 0) {
            out += '\n' + section('COMMANDS', this.subs.map(s => [s._name, s._description]));
        }
        const rows: [string, string][] = this.args.map(a => {
            let left = (a.short !== undefined ? `-${a.short}, ` : '    ') + `--${a.name}`;
            if (a.kind === 'flag') return [left, a.help];
            left += ' ' + PLACEHOLDER[a.type!];
            return [
                left,
                joinParts([a.help, a.default !== undefined ? `[default: ${a.default}]` : '', a.env !== undefined ? `[env: ${a.env}]` : '']),
            ];
        });
        rows.push(['    --help', 'Print help']);
        if (this._version !== undefined) rows.push(['    --version', 'Print version']);
        return out + '\n' + section('OPTIONS', rows);
    }

    /**
     * Parses a full command line (the first element is the program name) using
     * `process.env` for environment fallback when it exists.
     */
    parse(argv: readonly string[]): Matches {
        const env = (globalThis as { process?: { env?: Record<string, string | undefined> } }).process?.env ?? {};
        return this.parseWithEnv(argv.slice(1), name => env[name]);
    }

    /** Parses `tokens` (without the program name) with an explicit environment. */
    parseWithEnv(tokens: readonly string[], env: EnvLookup | Record<string, string | undefined> = {}): Matches {
        this.validate();
        const lookup: EnvLookup = typeof env === 'function' ? env : name => (Object.hasOwn(env, name) ? env[name] : undefined);
        return this.parseTokens(tokens, lookup, this._name);
    }

    /** Parses `process.argv` (Node.js). */
    parseEnv(): Matches {
        const argv = (globalThis as { process?: { argv?: string[] } }).process?.argv ?? [];
        return this.parse(argv.slice(1));
    }

    /**
     * Parses `process.argv`; prints help or version and exits with 0, or prints
     * the error and exits with 2 (Node.js).
     */
    run(): Matches {
        const proc = (globalThis as { process?: { stdout: { write(s: string): void }; stderr: { write(s: string): void }; exit(c: number): never } }).process!;
        try {
            return this.parseEnv();
        } catch (e) {
            if (!(e instanceof ParseError)) throw e;
            if (e.isInfo) {
                proc.stdout.write(e.text!);
                return proc.exit(0);
            }
            proc.stderr.write(`error: ${e.message}\n`);
            return proc.exit(2);
        }
    }

    private setOption(m: Matches, a: Named, raw: string, arg: string): void {
        const v = parseValue(a.type!, raw);
        if (v === undefined) throw new ParseError('INVALID_VALUE', arg, { value: raw });
        m._values.set(a.name, v);
        m._types.set(a.name, a.type!);
    }

    private parseTokens(tokens: readonly string[], env: EnvLookup, path: string): Matches {
        const m = new Matches();
        let posIdx = 0;
        let i = 0;
        let afterDD = false;
        while (i < tokens.length) {
            const tok = tokens[i]!;
            i++;
            if (!afterDD) {
                if (tok === '--') {
                    afterDD = true;
                    continue;
                }
                if (tok === '--help') throw new ParseError('HELP', '', { text: this.helpAt(path) });
                if (tok === '--version' && this._version !== undefined) {
                    throw new ParseError('VERSION', '', { text: `${this._name} ${this._version}\n` });
                }
                if (tok.startsWith('--')) {
                    const body = tok.slice(2);
                    const eq = body.indexOf('=');
                    const name = eq >= 0 ? body.slice(0, eq) : body;
                    let inline = eq >= 0 ? body.slice(eq + 1) : undefined;
                    const arg = `--${name}`;
                    const a = this.args.find(x => x.name === name);
                    if (!a) throw new ParseError('UNKNOWN_ARGUMENT', arg);
                    if (a.kind === 'flag') {
                        if (inline !== undefined) throw new ParseError('FLAG_TAKES_NO_VALUE', arg);
                        m._flags.add(a.name);
                        continue;
                    }
                    if (inline === undefined) {
                        if (i >= tokens.length) throw new ParseError('MISSING_VALUE', arg);
                        inline = tokens[i]!;
                        i++;
                    }
                    this.setOption(m, a, inline, arg);
                    continue;
                }
                if (tok.length > 1 && tok[0] === '-' && !/[0-9.]/.test(tok[1]!)) {
                    const cluster = [...tok.slice(1)];
                    for (let k = 0; k < cluster.length; k++) {
                        const c = cluster[k]!;
                        const arg = `-${c}`;
                        const a = this.args.find(x => x.short === c);
                        if (!a) throw new ParseError('UNKNOWN_ARGUMENT', arg);
                        if (a.kind === 'flag') {
                            m._flags.add(a.name);
                            continue;
                        }
                        let raw = cluster.slice(k + 1).join('');
                        if (raw.startsWith('=')) {
                            raw = raw.slice(1);
                        } else if (raw === '') {
                            if (i >= tokens.length) throw new ParseError('MISSING_VALUE', arg);
                            raw = tokens[i]!;
                            i++;
                        }
                        this.setOption(m, a, raw, arg);
                        break;
                    }
                    continue;
                }
            }
            if (!afterDD && this.subs.length > 0) {
                const sub = this.subs.find(s => s._name === tok);
                if (!sub) throw new ParseError('UNKNOWN_SUBCOMMAND', tok);
                m._sub = { name: tok, matches: sub.parseTokens(tokens.slice(i), env, `${path} ${tok}`) };
                break;
            }
            const p = this.positionals[posIdx];
            if (p) {
                const v = parseValue(p.type, tok);
                if (v === undefined) throw new ParseError('INVALID_VALUE', p.name, { value: tok });
                m._values.set(p.name, v);
                m._types.set(p.name, p.type);
                posIdx++;
            } else if (afterDD) {
                m._rest.push(tok);
            } else {
                throw new ParseError('UNEXPECTED_ARGUMENT', tok);
            }
        }
        for (const a of this.args) {
            if (a.kind !== 'option' || m._values.has(a.name)) continue;
            const fromEnv = a.env !== undefined ? env(a.env) : undefined;
            if (fromEnv !== undefined) this.setOption(m, a, fromEnv, `--${a.name}`);
            else if (a.default !== undefined) this.setOption(m, a, a.default, `--${a.name}`);
        }
        for (const p of this.positionals) {
            if (p.required && !m._values.has(p.name)) throw new ParseError('MISSING_REQUIRED', p.name);
        }
        return m;
    }
}
