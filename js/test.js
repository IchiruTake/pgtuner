const StringEnum = Object.freeze({
  RED: "RED",
  GREEN: "GREEN",
  BLUE: "BLUE",

  fromString(str) {
    return Object.values(StringEnum).includes(str) ? str : null;
  },

  equals(a, b) {
    return a === b;
  }
});

// Usage example
const userInput = "GREEN";
const userEnum = StringEnum.fromString(userInput);


console.log(StringEnum.equals(userEnum, StringEnum.GREEN)); // true
console.log(userEnum); // "GREEN"

const COLOR = Object.freeze({
  RED: 3,
  GREEN: 2,
  BLUE: 1
});

// Usage example
console.log(COLOR.GREEN < COLOR.RED); // true
console.log(COLOR.BLUE < COLOR.GREEN); // true
console.log(COLOR.RED > COLOR.BLUE); // true

const CUSTOM_COLOR = Object.freeze({
  RED: [3, 'red'],
  GREEN: [2, 'green'],
  BLUE: [1, 'blue'],
});
console.log(CUSTOM_COLOR.GREEN < CUSTOM_COLOR.BLUE); // true
console.log(COLOR.BLUE < COLOR.GREEN); // true
console.log(COLOR.RED > COLOR.BLUE); // true
let c_red = CUSTOM_COLOR([3, 'red']);   // Error


class StringEnum {
  constructor(value) {
    if (!StringEnum.values.includes(value)) {
      throw new Error(`Invalid value: ${value}`);
    }
    this.value = value;
  }

  static values = ["RED", "GREEN", "BLUE"];

  static RED = new StringEnum("RED");
  static GREEN = new StringEnum("GREEN");
  static BLUE = new StringEnum("BLUE");

  static fromString(str) {
    return Object.values(StringEnum).find(enumItem => enumItem.value === str) || null;
  }

  equals(otherEnum) {
    return otherEnum instanceof StringEnum && this.value === otherEnum.value;
  }

  toString() {
    return this.value;
  }
}

// Usage example
const userInput = "GREEN";
const userEnum = StringEnum.fromString(userInput);

console.log(userEnum === StringEnum.GREEN); // true
console.log(userEnum.equals(StringEnum.GREEN)); // true
console.log(userEnum.toString()); // "GREEN"
console.log(class userEnum == typeof StringEnum);

// List all enums sorted by value in ascending order
const sortedEnums = Object.entries(COLOR)
  .sort((a, b) => a[1] - b[1]) // Sort based on numeric value
  .map(([key]) => COLOR[key]); // Map back to enum instances

console.log(sortedEnums); // [COLOR.BLUE, COLOR.GREEN, COLOR.RED]
console.log(sortedEnums[2] === COLOR.RED)

