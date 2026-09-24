/**
 * LombokCLIParse — Lightweight CLI argument parser.
 *
 * Positional args, flags, options, subcommands, auto-help,
 * env fallback, type parsing. Zero dependencies.
 *
 * @example
 * ```ts
 * import { App, ArgType } from 'lombokcliparse';
 *
 * const app = new App('myapp', 'My application')
 *   .version('1.0.0')
 *   .positional('input', 'Input file', ArgType.Str, true)
 *   .flag('verbose', 'Enable verbose', 'v')
 *   .option('port', 'Port', ArgType.Int, 'p', '8080');
 *
 * const matches = app.parse(['myapp', 'data.txt', '--verbose', '-p', '3000']);
 * ```
 */

// ── Types ──────────────────────────────────────────────────────────

export enum ArgType {
  Str = 'str',
  Int = 'int',
  Bool = 'bool',
  Float = 'float',
}

export type Value = string | number | boolean;

export class ParseError extends Error {
  constructor(
    public kind: 'unknown_arg' | 'missing_required' | 'missing_value' | 'invalid_type' | 'unknown_subcommand',
    message: string,
  ) {
    super(message);
    this.name = 'ParseError';
  }
}

// ── Internal types ─────────────────────────────────────────────────

interface Positional {
  name: string;
  help: string;
  argType: ArgType;
  required: boolean;
}

interface Flag {
  name: string;
  help: string;
  short?: string;
}

interface Opt {
  name: string;
  help: string;
  argType: ArgType;
  short?: string;
  defaultVal?: string;
  envVar?: string;
}

// ── Matches ────────────────────────────────────────────────────────

export class Matches {
  private values = new Map<string, Value>();
  private flags = new Map<string, boolean>();
  private _subcommand?: { name: string; matches: Matches };
  private _rest: string[] = [];

  /** Get string value. */
  getStr(name: string): string | undefined {
    const v = this.values.get(name);
    return typeof v === 'string' ? v : undefined;
  }

  /** Get integer value. */
  getInt(name: string): number | undefined {
    const v = this.values.get(name);
    return typeof v === 'number' && Number.isInteger(v) ? v : undefined;
  }

  /** Get float value. */
  getFloat(name: string): number | undefined {
    const v = this.values.get(name);
    return typeof v === 'number' ? v : undefined;
  }

  /** Check if flag is set. */
  getBool(name: string): boolean {
    return this.flags.get(name) ?? false;
  }

  /** Get raw value. */
  get(name: string): Value | undefined {
    return this.values.get(name);
  }

  /** Get subcommand. */
  subcommand(): { name: string; matches: Matches } | undefined {
    return this._subcommand;
  }

  /** Remaining args after `--`. */
  rest(): string[] {
    return this._rest;
  }

  // Internal setters
  /** @internal */ _setValue(name: string, val: Value): void { this.values.set(name, val); }
  /** @internal */ _setFlag(name: string, val: boolean): void { this.flags.set(name, val); }
  /** @internal */ _setSubcommand(name: string, matches: Matches): void { this._subcommand = { name, matches }; }
  /** @internal */ _addRest(val: string): void { this._rest.push(val); }
}

// ── App ────────────────────────────────────────────────────────────

export class App {
  private _name: string;
  private _description: string;
  private _version?: string;
  private positionals: Positional[] = [];
  private flagDefs: Flag[] = [];
  private optDefs: Opt[] = [];
  private subcommands = new Map<string, App>();

  constructor(name: string, description: string) {
    this._name = name;
    this._description = description;
  }

  /** Set version string. */
  version(v: string): this {
    this._version = v;
    return this;
  }

  /** Add positional argument. */
  positional(name: string, help: string, argType: ArgType, required: boolean): this {
    this.positionals.push({ name, help, argType, required });
    return this;
  }

  /** Add boolean flag. */
  flag(name: string, help: string, short?: string): this {
    this.flagDefs.push({ name, help, short });
    return this;
  }

  /** Add key-value option. */
  option(
    name: string,
    help: string,
    argType: ArgType,
    short?: string,
    defaultVal?: string,
    envVar?: string,
  ): this {
    this.optDefs.push({ name, help, argType, short, defaultVal, envVar });
    return this;
  }

  /** Add subcommand. */
  sub(sub: App): this {
    this.subcommands.set(sub._name, sub);
    return this;
  }

  /** Generate help text. */
  help(): string {
    let out = this._name;
    if (this._version) out += ` ${this._version}`;
    out += `\n${this._description}\n\n`;

    out += `USAGE:\n    ${this._name}`;
    if (this.subcommands.size > 0) out += ' <COMMAND>';
    if (this.optDefs.length > 0 || this.flagDefs.length > 0) out += ' [OPTIONS]';
    for (const p of this.positionals) {
      out += p.required ? ` <${p.name.toUpperCase()}>` : ` [${p.name.toUpperCase()}]`;
    }
    out += '\n\n';

    if (this.positionals.length > 0) {
      out += 'ARGS:\n';
      for (const p of this.positionals) {
        const req = p.required ? ' (required)' : '';
        out += `    <${p.name.toUpperCase()}>    ${p.help}${req}\n`;
      }
      out += '\n';
    }

    if (this.subcommands.size > 0) {
      out += 'COMMANDS:\n';
      const sorted = [...this.subcommands.keys()].sort();
      for (const name of sorted) {
        const sub = this.subcommands.get(name)!;
        out += `    ${name.padEnd(16)}${sub._description}\n`;
      }
      out += '\n';
    }

    if (this.flagDefs.length > 0 || this.optDefs.length > 0) {
      out += 'OPTIONS:\n';
      for (const f of this.flagDefs) {
        const s = f.short ? `-${f.short}, ` : '    ';
        out += `    ${s}--${f.name.padEnd(16)}${f.help}\n`;
      }
      for (const o of this.optDefs) {
        const s = o.short ? `-${o.short}, ` : '    ';
        const def = o.defaultVal ? ` [default: ${o.defaultVal}]` : '';
        const env = o.envVar ? ` [env: ${o.envVar}]` : '';
        out += `    ${s}--${o.name.padEnd(16)}${o.help}${def}${env}\n`;
      }
      out += '        --help            Show this help message\n';
    }

    return out;
  }

  /** Parse args array (first element = program name, skipped). */
  parse(args: string[]): Matches {
    return this._parseSlice(args.slice(1));
  }

  /** Parse from process.argv. */
  parseEnv(): Matches {
    return this.parse(process.argv);
  }

  private _parseSlice(args: string[]): Matches {
    const matches = new Matches();
    let posIdx = 0;
    let i = 0;
    let afterDoubleDash = false;

    while (i < args.length) {
      const arg = args[i];

      if (afterDoubleDash) {
        matches._addRest(arg);
        i++;
        continue;
      }

      if (arg === '--') {
        afterDoubleDash = true;
        i++;
        continue;
      }

      // --name=value or --name value
      if (arg.startsWith('--')) {
        const rest = arg.slice(2);

        if (rest === 'help') {
          console.log(this.help());
          process.exit(0);
        }

        let name: string;
        let inlineVal: string | undefined;
        const eqIdx = rest.indexOf('=');
        if (eqIdx !== -1) {
          name = rest.slice(0, eqIdx);
          inlineVal = rest.slice(eqIdx + 1);
        } else {
          name = rest;
        }

        // Flag?
        const flagDef = this.flagDefs.find(f => f.name === name);
        if (flagDef) {
          matches._setFlag(name, true);
          i++;
          continue;
        }

        // Option?
        const optDef = this.optDefs.find(o => o.name === name);
        if (optDef) {
          let valStr: string;
          if (inlineVal !== undefined) {
            valStr = inlineVal;
          } else {
            i++;
            if (i >= args.length) throw new ParseError('missing_value', `missing value for: --${name}`);
            valStr = args[i];
          }
          matches._setValue(optDef.name, parseValue(optDef.name, valStr, optDef.argType));
          i++;
          continue;
        }

        throw new ParseError('unknown_arg', `unknown argument: --${name}`);
      }

      // Short flags/options: -v, -p value, -vn
      if (arg.startsWith('-') && arg.length > 1 && !arg.startsWith('--')) {
        const chars = arg.slice(1).split('');
        let ci = 0;
        while (ci < chars.length) {
          const ch = chars[ci];

          const flagDef = this.flagDefs.find(f => f.short === ch);
          if (flagDef) {
            matches._setFlag(flagDef.name, true);
            ci++;
            continue;
          }

          const optDef = this.optDefs.find(o => o.short === ch);
          if (optDef) {
            let valStr: string;
            if (ci + 1 < chars.length) {
              valStr = chars.slice(ci + 1).join('');
            } else {
              i++;
              if (i >= args.length) throw new ParseError('missing_value', `missing value for: ${optDef.name}`);
              valStr = args[i];
            }
            matches._setValue(optDef.name, parseValue(optDef.name, valStr, optDef.argType));
            break;
          }

          throw new ParseError('unknown_arg', `unknown argument: -${ch}`);
        }
        i++;
        continue;
      }

      // Subcommand?
      if (posIdx === 0 && this.subcommands.has(arg)) {
        const sub = this.subcommands.get(arg)!;
        const subMatches = sub._parseSlice(args.slice(i + 1));
        matches._setSubcommand(arg, subMatches);
        return matches;
      }

      // Positional
      if (posIdx < this.positionals.length) {
        const p = this.positionals[posIdx];
        matches._setValue(p.name, parseValue(p.name, arg, p.argType));
        posIdx++;
      } else {
        matches._addRest(arg);
      }

      i++;
    }

    // Defaults and env vars
    for (const o of this.optDefs) {
      if (matches.get(o.name) === undefined) {
        if (o.envVar) {
          const envVal = process.env[o.envVar];
          if (envVal !== undefined) {
            try {
              matches._setValue(o.name, parseValue(o.name, envVal, o.argType));
              continue;
            } catch { /* fallthrough to default */ }
          }
        }
        if (o.defaultVal !== undefined) {
          try {
            matches._setValue(o.name, parseValue(o.name, o.defaultVal, o.argType));
          } catch { /* skip */ }
        }
      }
    }

    // Required check
    for (const p of this.positionals) {
      if (p.required && matches.get(p.name) === undefined) {
        throw new ParseError('missing_required', `missing required argument: ${p.name}`);
      }
    }

    return matches;
  }
}

function parseValue(name: string, raw: string, ty: ArgType): Value {
  switch (ty) {
    case ArgType.Str:
      return raw;
    case ArgType.Int: {
      const n = parseInt(raw, 10);
      if (isNaN(n)) throw new ParseError('invalid_type', `invalid value '${raw}' for ${name}`);
      return n;
    }
    case ArgType.Float: {
      const n = parseFloat(raw);
      if (isNaN(n)) throw new ParseError('invalid_type', `invalid value '${raw}' for ${name}`);
      return n;
    }
    case ArgType.Bool:
      if (['true', '1', 'yes', 'on'].includes(raw)) return true;
      if (['false', '0', 'no', 'off'].includes(raw)) return false;
      throw new ParseError('invalid_type', `invalid value '${raw}' for ${name}`);
  }
}
