export declare const BUNDLE_FILE: '.nova-bundled.json';
export declare const BUNDLED_BY: 'Nova AI Skills';
/** The skills folder of this package. */
export declare const SKILLS_DIR: string;
export declare const VERSION: string;
/** SHA-256 over the names and contents of a skill's files. */
export declare function hashSkill(root: string): Promise<string>;
/** Compares two semver versions; a prerelease sorts before its release. */
export declare function compareVersions(a: string, b: string): -1 | 0 | 1;
/** Installs or updates the skills under `<novaHome>/skills`; returns the names it (re)installed. */
export declare function installSkills(novaHome: string, options?: { sourceDir?: string; version?: string }): Promise<string[]>;
