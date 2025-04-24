// import { ByteSize } from 'pydantic'; // Assuming a similar library exists in JavaScript
import { DB_PAGE_SIZE } from './js_src/static.js';


const bytesize_to_hr = (bytesize, decimal = false, separator = ' ') => {
    /**
     * Converts a byte size to a human-readable string.
     * Arguments:
     * ---------
     * bytesize : int | float
     *   The byte size to convert.
     * 
     * decimal : bool
     *  If True, use decimal units (e.g. 1000 bytes per KB). If False, use binary units (e.g. 1024 bytes per KiB).
     * 
     * separator : str
     *  A string used to split the value and unit. Defaults to an empty string ('').
     * 
     * Returns:
     * -------
     * * str
     *   A human-readable string representation of the byte size.
     */
    if (typeof bytesize === 'number') {
        bytesize = Math.floor(bytesize);
    }
    if (bytesize === 0) {
        return `0${separator}B`;
    }
    if (bytesize < 0) {
        throw new Error('Negative byte size is not supported');
    }
    if (decimal) {
        let divisor = 1000;
        let units = ['B', 'KB', 'MB', 'GB', 'TB', 'PB'];
        let final_unit = 'EB';
    } else {
        let divisor = 1024;
        let units = ['B', 'KiB', 'MiB', 'GiB', 'TiB', 'PiB'];
        let final_unit = 'EiB';
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

const realign_value = (value, page_size = DB_PAGE_SIZE) => {
    // This function is used to ensure we re-align the :var:`value` to the nearest page size
    const d = Math.floor(value / page_size);
    const m = value % page_size;
    return [d * page_size, (d + (m > 0 ? 1 : 0)) * page_size];
}

const cap_value = (value, min_value, max_value, redirectNumber = null) => {
    if (redirectNumber && redirectNumber.length === 2 && value === redirectNumber[0]) {
        value = redirectNumber[1];
    }
    return min(max(value, min_value), max_value);
};

export { bytesizeToHr, realign_value, cap_value };
