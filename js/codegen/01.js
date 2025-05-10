// ================================================================================
/**
 * Original Source File: ./src/utils/pydantic_utils.py
 * This file is part of the pgtuner project, containing static variables and constants such as
 * application information, instruction identification, timing constants, hard-coded values, and
 * regular expression patterns.
 */

/**
 * Converts a byte size to a human-readable string.
 *
 * @param {number} bytesize - The byte size to convert.
 * @param {boolean} [decimal=false] - If true, use decimal units (e.g. 1000 bytes per KB). If false, use binary units (e.g. 1024 bytes per KiB).
 * @param {string} [separator=' '] - A string used to split the value and unit. Defaults to an empty whitespace string (' ').
 * @returns {string} - A human-readable string representation of the byte size.
 */
const bytesize_to_hr = (bytesize, decimal = false, separator = ' ') => {
    if (typeof bytesize !== 'number') {
        bytesize = Math.floor(bytesize);
    }
    if (bytesize === 0) {
        return `0${separator}B`;
    }
    if (bytesize < 0) {
        throw new Error('Negative byte size is not supported');
    }
    let divisor, units, final_unit;
    if (decimal) {
        divisor = 1000;
        units = ['B', 'KB', 'MB', 'GB', 'TB', 'PB'];
        final_unit = 'EB';
    } else {
        divisor = 1024;
        units = ['B', 'KiB', 'MiB', 'GiB', 'TiB', 'PiB'];
        final_unit = 'EiB';
    }
    let num = bytesize;
    for (let unit of units) {
        if (Math.abs(num) < divisor) {
            if (unit === 'B') {
                return `${num.toFixed(0)}${separator}${unit}`;
            } else {
                return `${num.toFixed(1)}${separator}${unit}`;
            }
        }
        num /= divisor;
    }
    return `${num.toFixed(1)}${separator}${final_unit}`;
}

/**
 * This function is used to ensure we re-align the :var:`value` to the nearest :var:`page_size`
 * so that the modified :var:`value` is a multiple of the :var:`page_size`.
 * @param {number} value - The value to be realigned.
 * @param {number} page_size - The page size to align to. Default is 8 * 1024 (8 KiB).
 * @returns {Array<number>} - An array containing the lower and upper bounds of the realigned value.
 */
const realign_value = (value, page_size = DB_PAGE_SIZE) => {
    if (typeof value === 'number') {
        value = Math.floor(value);
    }
    const d = Math.floor(value / page_size);
    const m = value % page_size;
    return [d * page_size, (d + (m > 0 ? 1 : 0)) * page_size];
}

/**
 * This function is used to ensure the :var:`value` is casted under the range of :var:`min_value`
 * and :var:`max_value`.
 *
 * @param {number} value - The value to be capped.
 * @param {number} min_value - The minimum value.
 * @param {number} max_value - The maximum value.
 * @param {Array<number>} [redirectNumber=null] - An optional array containing two numbers. If the
 * value is equal to the first number, it will be replaced by the second number.
 * @returns {number} - The capped value.
 */
const cap_value = (value, min_value, max_value, redirectNumber = null) => {
    if (redirectNumber && redirectNumber.length === 2 && value === redirectNumber[0]) {
        value = redirectNumber[1];
    }
    return Math.min(Math.max(value, min_value), max_value);
};

// =================================================================================
/**
 * Original Source File: ./src/utils/mean.py
 */

/**
 * Calculate the generalized mean of the given arguments and rounding to the specified number of digits.
 * This function is used to calculate the average of the given arguments using the power of the level.
 * If level = 1, it will be the same as the normal average.
 * Ref: https://en.wikipedia.org/wiki/Generalized_mean
 *
 * Parameters
 * ----------
 * @param {number[]} x - The series of numbers to be averaged.
 * @param {number} level - The level of the generalized mean.
 * @param {number} round_ndigits - The number of digits to round to.
 *
 * Example
 * -------
 * generalized_mean([1, 2], 1, 4)  // returns 1.5
 * generalized_mean([1, 2], -6, 4)  // returns 1.1196
 */
function generalized_mean(x, level, round_ndigits = 4) {
    if (level === 0) {
        level = 1e-6; // Small value to prevent division by zero
    }
    const n = x.length;
    const sumPower = x.reduce((acc, val) => acc + Math.pow(val, level), 0);
    const result = Math.pow(sumPower / n, 1 / level);

    // Rounding the number to the specified number of digits
    if (round_ndigits !== null) {
        if (typeof round_ndigits !== 'number') {
            throw new Error("The 'round_ndigits' property must be a number.");
        }

        if (round_ndigits < 0) {
            throw new Error("The 'round_ndigits' property must be a non-negative number.");
        }
    }
    const factor = Math.pow(10, round_ndigits);
    return Math.round(result * factor) / factor;
}

