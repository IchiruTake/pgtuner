import os.path
import shutil
from typing import Literal
import httpx

def cleanup_css(website_url: str, store_path: str = './web/ui/static', backup: bool = False):
    from mincss.processor import Processor
    p = Processor(debug=True)
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


def cleanup_html(html_file: str):
    import minify_html
    with open(html_file, 'r') as f:
        html_doc = f.read()
        minified_html = minify_html.minify(code=html_doc, minify_css=True, minify_js=True)
        if html_file.endswith('.html'):
            minified_html_filepath = html_file[:-5] + '.min.html'
        else:
            minified_html_filepath = html_file.replace('.html', '.min.html')
        with open(minified_html_filepath, 'w') as f_min:
            f_min.write(minified_html)
        return minified_html_filepath

def cleanup_js(js_file: str, client: httpx.Client):
    url = 'https://www.toptal.com/developers/javascript-minifier/api/raw'
    with open(js_file, 'r') as f:
        response = client.post(url, data={'input': f.read()})
        if js_file.endswith('.js'):
            minified_js_filepath = js_file[:-3] + '.min.js'
        else:
            minified_js_filepath = js_file.replace('.js', '.min.js')
        if response.status_code // 100 == 2:
            minified_js = response.text
            with open(minified_js_filepath, 'w') as f_min:
                f_min.write(minified_js)
            return minified_js_filepath
        else:
            print(f'Failed to minify the JS file: {js_file}')
            return None


def chrome_coverage_to_css_js_html(json_file: str, store_path: str = './'):
    # DO NOT USE
    import json

    with open(json_file, 'r') as f:
        data = json.load(f)
        for rq in data:
            url_value: str = rq['url']
            url_text = rq['text']
            filename = url_value.split('/')[-1]
            file_crack = filename.split('.')
            file_crack[-1] = f'chrome.{file_crack[-1]}'
            new_filename = '.'.join(file_crack)

            content = [url_text[scope['start']:scope['end']] for scope in rq['ranges']]
            with open(os.path.join(store_path, new_filename), 'w') as f_url:
                f_url.write(''.join(content))
    pass


def migrate(dev_path: str = './web/ui/dev/static', prod_path: str = './web/ui/prd/static',
            old_html_treatment: Literal['replace', 'backup', 'remove', 'skip'] = 'replace',
            old_js_treatment: Literal['replace', 'backup', 'remove', 'skip'] = 'replace'):
    if dev_path != prod_path:
        # If same directory, skip the cleanup and copy
        # Remove the existing prod_path
        if os.path.exists(prod_path):
            shutil.rmtree(prod_path)

        # Copy the dev_path to prod_path
        shutil.copytree(dev_path, prod_path)

    # Scan the whole directory recursively, then apply the HTML minification if the file extension is .html
    client = httpx.Client()
    for root, dirs, files in os.walk(prod_path):
        for file in files:
            if file.endswith('.html'):
                if file.endswith('.min.html'):
                    # Skip the minified HTML
                    print(f'Skip the minified HTML file: {os.path.join(root, file)}')
                    continue

                html_filepath = os.path.join(root, file)
                minified_html_filepath = cleanup_html(html_filepath)
                print(f'Found HTML file: {html_filepath} --> {minified_html_filepath} :: Resolve legacy HTML by {old_html_treatment}')
                match old_html_treatment:
                    case 'replace':
                        os.remove(html_filepath)
                        shutil.copy(minified_html_filepath, html_filepath)
                    case 'backup':
                        os.rename(html_filepath, html_filepath + '.bak')
                    case 'remove':
                        os.remove(html_filepath)
            if file.endswith('.js'):
                if file.endswith('.min.js'):
                    # Skip the minified JS
                    print(f'Skip the minified JS file: {os.path.join(root, file)}')
                    continue
                js_filepath = os.path.join(root, file)
                minified_js_filepath = cleanup_js(js_filepath, client)
                print(f'Found JS file: {js_filepath} --> {minified_js_filepath} :: Resolve legacy JS by {old_js_treatment}')
                match old_js_treatment:
                    case 'replace':
                        os.remove(js_filepath)
                        shutil.copy(minified_js_filepath, js_filepath)
                    case 'backup':
                        os.rename(js_filepath, js_filepath + '.bak')
                    case 'remove':
                        os.remove(js_filepath)
    client.close()

    return None


if __name__ == '__main__':
    store_path = './web/ui/dev/static'
    url = 'http://localhost:8001/static/index.html'
    # url = 'http://192.168.0.175:8001/static/index.html'
    # url = 'https://pgtuner.onrender.com/static/index.html'
    # cleanup_css(url, store_path, backup=False)

    # cleanup_html(f'{store_path}/index.html')

    # chrome_coverage_to_css_js_html('./Coverage-20250124T221919.json')

    # Proceed the PRD first then DEV later
    migrate(dev_path='./web/ui/dev/static', prod_path='./web/ui/prd/static',
            old_html_treatment='replace', old_js_treatment='skip')
    migrate(dev_path='./web/ui/dev/static', prod_path='./web/ui/dev/static',
            old_html_treatment='skip', old_js_treatment='skip')
    print('Done')
