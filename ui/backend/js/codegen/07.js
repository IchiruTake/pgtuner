// ==================================================================================
/**
 * Original Source File: ./src/tuner/profile/database/gtune_13.py
 */

const DB13_CONFIG_PROFILE = { };
// Pseudo Deep Copy
for (const [key, value] of Object.entries(DB0_CONFIG_PROFILE)) {
    DB13_CONFIG_PROFILE[key] = [value[0], { ...value[1] }, value[2]];
}

// console.debug(`DB13_CONFIG_PROFILE`);
// show_profile(DB13_CONFIG_PROFILE);