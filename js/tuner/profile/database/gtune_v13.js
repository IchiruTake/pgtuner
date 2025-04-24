// -------------------------------------------------------------------
import { DB0_CONFIG_PROFILE } from './gtune_0.js';

// DB13_CONFIG_MAPPING is an empty object currently
const DB13_CONFIG_MAPPING = {};

// If DB13_CONFIG_MAPPING is non-empty, make a shallow copy of DB0_CONFIG_PROFILE;
// otherwise, use DB0_CONFIG_PROFILE directly.
const DB13_CONFIG_PROFILE = Object.keys(DB13_CONFIG_MAPPING).length > 0
    ? { ...DB0_CONFIG_PROFILE }
    : DB0_CONFIG_PROFILE;

export { DB13_CONFIG_PROFILE };
console.debug(`DB13_CONFIG_PROFILE: ${JSON.stringify(DB13_CONFIG_PROFILE)}`);
