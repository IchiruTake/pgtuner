import os.path

def cleanup_css(website_url: str, store_path: str = './web/ui/static', backup: bool = False):
    from mincss.processor import Processor
    p = Processor()
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
        with open(html_file.replace('.html','.min.html'), 'w') as f_min:
            f_min.write(minified_html)

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


if __name__ == '__main__':
    url = 'http://localhost:8001/static/index.html'
    # url = 'http://192.168.0.175:8001/static/index.html'
    # url = 'https://pgtuner.onrender.com/static/index.html'
    # cleanup_css(url, backup=False)

    cleanup_html('./web/ui/static/index.html')

    # chrome_coverage_to_css_js_html('./Coverage-20250124T221919.json')

    print('Done')
