// -------------------------------------------------------------------------------------
const _FLOAT_PRECISION = 4; // Default float precision for PG_TUNE_ITEM
// The string punctuation characters
const _STRING_PUNCTUATION = String.raw(""!"#$%&'()*+,-./:;<=>?@[\]^_`{|}~"");

class PG_TUNE_ITEM {
    constructor(data) {
        // Required fields
        this.key = data.key;
        this.before = data.before;
        this.after = data.after;
        this.comment = data.comment || null;

        // Custom-reserved variables for developers
        this.style = data.style !== undefined ? data.style : "$1 = '$2'";
        this.trigger = data.trigger;
        this.partial_func = data.partial_func || null;
        this.hardware_scope = data.hardware_scope; // Expected as a tuple [hardware type, sizing value]
    }

    out(output_if_difference_only = false, include_comment = false, custom_style = null) {
        // If output_if_difference_only is true and before equals after, return an empty string.
        if (output_if_difference_only && this.before === this.after) {
            return '';
        }
        let texts = [];

        if (include_comment && this.comment !== null) {
            // Transform the comment by prefixing each line with "# "
            const formattedComment = String(this.comment)
                .split('\n')
                .map(line => `# ${line}`)
                .join('\n');
            texts.push(formattedComment);
        }

        const style = custom_style || this.style || "$1 = $2";
        if (!style.includes("$1") || !style.includes("$2")) {
            throw new Error(`Invalid style configuration: ${style} due to missing $1 and $2`);
        }
        // Remove duplicated spaces if present
        const cleanedStyle = style.replace(/\s\s+/g, ' ');
        const afterDisplay = this.out_display();
        const resultStyle = cleanedStyle.replace("$1", this.key).replace("$2", afterDisplay).trim();

        texts.push(resultStyle);
        return texts.join('');
    }

    out_display(override_value = null) {
        let value = override_value !== null ? override_value : this.after;

        if (this.partial_func && typeof this.partial_func === 'function') {
            value = this.partial_func(value);
        } else if (typeof value === 'number') {
            // Rounding and converting to fixed point string
            value = value.toFixed(_FLOAT_PRECISION);
            // Remove trailing zeros and possible trailing dot
            value = value.replace(/(\.\d*?[1-9])0+$/,'$1').replace(/\.0+$/,'').replace(/\.$/, '.0');
        }
        if (typeof value !== 'string') {
            value = String(value);
        }
        // Trim whitespace if value contains a decimal point and remove trailing zeros
        if (value.includes('.')) {
            value = value.trim().replace(/(\.\d*?)0+$/, '$1');
            if (value.endsWith('.')) {
                value += '0';
            }
        }
        // If the original after value is a string that contains whitespace or punctuation, wrap it in single quotes.
        if (typeof this.after === 'string' &&
            (this.after.includes(' ') || _STRING_PUNCTUATION.split('').some(p => this.after.includes(p)))) {
            value = `'${value}'`;
        }

        if (typeof this.after === 'string' &&
            (this.after.includes(' ') || )) {
            value = `'${value}'`;
        }
        return value;
    }

    transform_keyname() {
        return this.key.split('_').map(part => part.charAt(0).toUpperCase() + part.slice(1)).join(' ');
    }
}

module.exports = { PG_TUNE_ITEM };