class PG_SIZING {
  constructor(value) {
    if (typeof value == 'string') { 
        if (!PG_SIZING.values.includes(value)) { 
            throw new Error(`Invalid value: ${value}`);
        } 
    }  else if (typeof value == 'number') {
        value = PG_SIZING.values[value];
    } else {
      throw new Error(`Invalid value: ${value}`);
    }
    this.value = value;
  }

  static values = ['mini', 'medium', 'large', 'mall', 'bigt'];
  static MINI = new PG_SIZING('mini');
  static MEDIUM = new PG_SIZING('medium');
  static LARGE = new PG_SIZING('large');
  static MALL = new PG_SIZING('mall');
  static BIGT = new PG_SIZING('bigt');

  static fromString(str) {
    return new PG_SIZING(str)
  }

  num() {
    return PG_SIZING.values.findIndex(t => t === this.value);
  }

  equals(otherEnum) {
    return this.num() == otherEnum.num();
  }

  toString() {
    return this.value;
  }
  
  valueOf() {
    return this.value;
  }

  [Symbol.toPrimitive](hint) {
    if (hint === "number") {
      return this.num();
    }
    if (hint === "string") {
      return this.value;
    } 
    return this.value;
  }
}

// Usage example
const userInput = "mini";
const userEnum = PG_SIZING.fromString(userInput);
// true
console.log(userEnum);
console.log(PG_SIZING.MINI);
console.log(userEnum + 0);
console.log(PG_SIZING.LARGE + 1);


console.log(userEnum == PG_SIZING.MINI);
console.log(userEnum === PG_SIZING.MINI);
console.log(userEnum.value == PG_SIZING.MINI.value);
console.log(userEnum.value === PG_SIZING.MINI.value);
console.log(userEnum.equals(PG_SIZING.MINI));
console.log(Object.is(userEnum, PG_SIZING.MINI));

console.log('------------------------------');
console.log(userEnum < PG_SIZING.MEDIUM);
console.log(userEnum < PG_SIZING.LARGE);
console.log(userEnum < PG_SIZING.MALL);
console.log(userEnum < PG_SIZING.BIGT);
console.log(PG_SIZING.MEDIUM < PG_SIZING.MEDIUM);
console.log(PG_SIZING.MEDIUM < PG_SIZING.LARGE);
console.log(PG_SIZING.MALL < PG_SIZING.BIGT);