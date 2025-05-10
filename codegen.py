"""
This module is to combine multiple of Javascript code snippets into a single file for pgtuner.
This code snippets are made to minimize the extremely large size of the Javascript code.

"""

import os

if __name__ == "__main__":
    codegen_input_dirpath = './js/codegen'
    codegen_output_filepath = './js/codegen.js'
    if not os.path.exists(codegen_input_dirpath):
        raise FileNotFoundError(f"Input directory '{codegen_input_dirpath}' does not exist.")
    if os.path.exists(codegen_output_filepath):
        os.remove(codegen_output_filepath)

    # List all filename in the input directory, and sorted based on the number
    files = []
    for filename in os.listdir(codegen_input_dirpath):
        if filename.endswith('.js'):
            files.append(filename)
    files.sort(key=lambda x: int(x.split('.')[0]))
    # print(files)

    with open(codegen_output_filepath, 'w', encoding='utf8') as codegen_output_file:
        for filename in files:
            codegen_input_filepath = os.path.join(codegen_input_dirpath, filename)
            with open(codegen_input_filepath, 'r', encoding='utf8') as codegen_input_file:
                codegen_output_file.write(codegen_input_file.read())
                codegen_output_file.write('\n\n')




