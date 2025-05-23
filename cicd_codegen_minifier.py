"""
This module is to combine multiple of Javascript code snippets into a single file for pgtuner.
This code snippets are made to minimize the extremely large size of the Javascript code.

Remember to set working directory to be equal to this file.

Installation Requirements:
minify-html
mincss
rjsmin
-> pip install minify-html mincss rjsmin

"""

import os
import os.path
import shutil
from time import perf_counter
from typing import Literal, Any
from jinja2 import Environment, FileSystemLoader

def cleanup_css_local(website_url: str, store_path: str = './web/ui/static', backup: bool = False):
    try:
        from mincss.processor import Processor
    except (ImportError, ModuleNotFoundError):
        print('Please install mincss package')
        return None

    p = Processor(debug=True, preserve_remote_urls=True, optimize_lookup=True)
    p.process(website_url)
    print('Inlines CSS discovered:', len(p.inlines))
    print('External CSS discovered:', len(p.links))
    if p.inlines:
        for i, inline_css in enumerate(p.inlines):
            if backup:
                with open(os.path.join(store_path, f'inline_{i:03}.css'), 'w') as f:
                    f.write(inline_css.before)
            with open(os.path.join(store_path, f'inline_{i:03}_min.css'), 'w') as f:
                f.write(inline_css.after)
    if p.links:
        for i, link_css in enumerate(p.links):
            if backup:
                with open(os.path.join(store_path, f'link_{i:03}.css'), 'w') as f:
                    f.write(link_css.before)
            with open(os.path.join(store_path, f'link_{i:03}_min.css'), 'w') as f:
                f.write(link_css.after)

    return None

def _write_minified_file(content: Any, original_filepath: str, extra_newline: bool = False):
    dirname: str = os.path.dirname(original_filepath)
    filename, extension = os.path.splitext(os.path.basename(original_filepath))
    minified_filepath = os.path.join(dirname, filename + '.min' + extension)
    if os.path.exists(minified_filepath):
        os.remove(minified_filepath)
    with open(minified_filepath, 'w', encoding='utf8') as f_min:
        f_min.write(content)
        if extra_newline:
            f_min.write('\n')
    src_filesize = os.path.getsize(original_filepath)
    minified_filesize = os.path.getsize(minified_filepath)
    print(f'Compression on {original_filepath}: {minified_filesize / src_filesize * 100:.2f}% -> '
          f'Saving {src_filesize - minified_filesize} bytes')
    return minified_filepath

def cleanup_html_local(html_file: str):
    try:
        import minify_html
    except (ImportError, ModuleNotFoundError):
        print('Please install minify_html package')
        return None

    with open(html_file, 'r', encoding='utf8') as f:
        minified_html = minify_html.minify(code=f.read(), minify_css=True, minify_js=True)
        return _write_minified_file(minified_html, html_file)

def cleanup_js_local(js_file: str):
    try:
        import rjsmin
    except (ImportError, ModuleNotFoundError):
        print('Please install jsmin package')
        return None

    with open(js_file, 'r', encoding='utf8') as f:
        minified_js = rjsmin.jsmin(f.read())
        return _write_minified_file(minified_js, js_file)

def migrate(src_path: str, tgt_path: str,
            old_html_treatment: Literal['replace', 'backup', 'remove', 'skip', 'override'] = 'replace',
            old_js_treatment: Literal['replace', 'backup', 'remove', 'skip', 'override'] = 'replace'):
    def _resolve_old_asset(origin: str, target: str | None, treatment: str) -> None:
        if target is None:
            return None

        if treatment == 'replace':
            os.remove(origin)
            shutil.copy(target, origin)
        elif treatment == 'backup':
            os.rename(origin, origin + '.bak')
        elif treatment == 'remove':
            os.remove(origin)
        elif treatment == 'skip':
            pass
        elif treatment == 'override':
            shutil.copy(target, origin)
            os.remove(target)
        return None

    if src_path != tgt_path:
        # If same directory, skip the cleanup and copy
        # Remove the existing prod_path
        if os.path.exists(tgt_path):
            shutil.rmtree(tgt_path)

        # Copy the dev_path to prod_path
        shutil.copytree(src_path, tgt_path)

    # Scan the whole directory recursively, then apply the HTML minification if the file extension is .html
    # client = httpx.AsyncClient()
    for root, dirs, files in os.walk(tgt_path):
        for file in files:
            src_filepath: str = os.path.join(root, file)
            src_file_extension = os.path.splitext(src_filepath)
            if '.min.' in file:
                # Skip the minified files
                continue
            minified_filepath = None
            if src_file_extension[1].endswith('html'):
                minified_filepath = cleanup_html_local(src_filepath)
                _resolve_old_asset(src_filepath, minified_filepath, old_html_treatment)
            elif src_file_extension[1].endswith('js'):
                minified_filepath = cleanup_js_local(src_filepath)
                _resolve_old_asset(src_filepath, minified_filepath, old_js_treatment)
            if minified_filepath is None:
                continue
            print(f'Found {src_file_extension[1].upper()[1:]} file: {src_filepath} --> {minified_filepath}'
                  f'\n\t-> Resolve legacy {src_file_extension[1].upper()[1:]} file by {old_html_treatment}')
    return None


if __name__ == "__main__":
    codegen_input_dirpath = 'ui/backend/js/codegen'
    codegen_output_filepath = 'ui/backend/js/codegen.js'
    dev_path = 'ui/dev'
    prod_path = 'ui/prod'
    jinja_src_path = 'ui/dev/jinja2'
    jinja_tgt_path = 'ui/frontend'
    jinja_files = [
        ('tuner.html', 'tuner.html'),
        ('error/index.html', 'error.html'),
        ('changelog.html', 'changelog.html'),
    ]
    jinja_cleanup_file = True   # Set to False to keep up the intermediate files

    jinja_js_min_dirpath = f'{jinja_tgt_path}/js'
    jinja_js_min_files = ['ui/backend/js/pgtuner.js', 'ui/backend/js/ui.js']

    # --------------------------------------------------
    # [01]: Javascript-backend CodeGen Merging and Minification
    t = perf_counter()
    print('Start merging the codegen files ...')
    if not os.path.exists(codegen_input_dirpath):
        raise FileNotFoundError(f"Input directory '{codegen_input_dirpath}' does not exist.")
    if os.path.exists(codegen_output_filepath):
        os.remove(codegen_output_filepath)

    # List all filename in the input directory, and sorted based on the number
    extra_condition = lambda x: int(x.split('.')[0]) < 99
    codegen_files = [filename for filename in os.listdir(codegen_input_dirpath)
                     if filename.endswith('.js') and extra_condition(filename)]
    codegen_files.sort(key=lambda x: int(x.split('.')[0]))
    # print(files)

    with open(codegen_output_filepath, 'w', encoding='utf8') as codegen_output_file:
        for filename in codegen_files:
            codegen_input_filepath = os.path.join(codegen_input_dirpath, filename)
            with open(codegen_input_filepath, 'r', encoding='utf8') as codegen_input_file:
                data = codegen_input_file.read()
                codegen_output_file.write(data)
                codegen_output_file.write('\n\n')
    cleanup_js_local(codegen_output_filepath)
    print(f'Codegen merging and minification completed in {1e3 * (perf_counter() - t):.2f} ms.')

    # --------------------------------------------------
    # [02]: Assets Minification
    t = perf_counter()
    print('-' * 40)
    print(f'Start minifying the assets from {dev_path} to {prod_path} ...')
    migrate(dev_path, prod_path, old_html_treatment='remove', old_js_treatment='remove')
    print(f'Assets minification from {dev_path} to {prod_path} completed in {1e3 * (perf_counter() - t):.2f} ms.')

    t = perf_counter()
    print('-' * 40)
    print(f'Start minifying the assets from {dev_path} to {dev_path} ...')
    migrate(dev_path, dev_path, old_html_treatment='skip', old_js_treatment='skip')
    print(f'Assets minification from {dev_path} to {dev_path} completed in {1e3 * (perf_counter() - t):.2f} ms.')

    # --------------------------------------------------
    # [03]: Compile the Jinja2 template
    t = perf_counter()
    print('-' * 40)
    print(f'Start compiling the Jinja2 template from {jinja_src_path} to {jinja_tgt_path} ...')
    os.makedirs(jinja_tgt_path, exist_ok=True)
    env = Environment(loader=FileSystemLoader(jinja_src_path), cache_size=400 * 10)
    for jinja_src_file, jinja_tgt_file in jinja_files:
        template = env.get_template(jinja_src_file)
        jinja_tgt_filepath = os.path.join(jinja_tgt_path, jinja_tgt_file)
        if os.path.exists(jinja_tgt_filepath):
            os.remove(jinja_tgt_filepath)
        with open(jinja_tgt_filepath, "w", encoding='utf8') as fh:
            fh.write(template.render())
        jinja_tgt_min_filepath = cleanup_html_local(jinja_tgt_filepath)
        if jinja_cleanup_file:
            # Remove the intermediate file
            os.remove(jinja_tgt_filepath) # Cleanup to free up some space
        if jinja_tgt_file.startswith('tuner'):
            # Copy it to index.html (tuner.min.html -> index.html)
            shutil.copy(jinja_tgt_min_filepath, os.path.join(jinja_tgt_path, 'index.html'))
        print('Compiled Jinja2 template:', jinja_src_file, '->', jinja_tgt_file, '->', jinja_tgt_min_filepath)
    print(f'Jinja2 template compilation completed in {1e3 * (perf_counter() - t):.2f} ms.')

    # -------------------------------------------------
    # [04]: Minify and Copy the JS to frontend
    t = perf_counter()
    print('-' * 40)
    print(f'Start minifying the JS files to {jinja_js_min_dirpath}')
    jinja_js_min_files.append(codegen_output_filepath)
    os.makedirs(jinja_js_min_dirpath, exist_ok=True)
    for jinja_js_file in jinja_js_min_files:
        jinja_js_min_filepath = cleanup_js_local(jinja_js_file)
        # Move the file to the target directory
        if jinja_js_min_filepath is None:
            print('Error: Failed to minify the JS file:', jinja_js_file)
            continue
        shutil.copy(jinja_js_min_filepath, jinja_js_min_dirpath)
        if os.path.exists(jinja_js_min_filepath):
            os.remove(jinja_js_min_filepath)
        print(f'The JS backend file {jinja_js_file} has been minified and copied to: {jinja_js_min_dirpath}')

    # -------------------------------------------------
    # [05]: Deploy to GitHub pages
    t = perf_counter()
    print('-' * 40)
    print(f'Start deploying to GitHub pages ...')
    gh_page_dirpath = './docs'
    if os.path.exists(gh_page_dirpath):
        shutil.rmtree(gh_page_dirpath)
    shutil.copytree(jinja_tgt_path, gh_page_dirpath)
    print(f'GitHub pages deployment completed in {1e3 * (perf_counter() - t):.2f} ms.')