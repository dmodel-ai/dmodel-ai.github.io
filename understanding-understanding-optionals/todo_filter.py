#!/usr/bin/python
import panflute as pf

def latex_todo_to_html(elem, doc):
    if isinstance(elem, pf.RawInline) and elem.format == 'tex':
        if elem.text.startswith(r"\todo{") and elem.text.endswith("}"):
            content = elem.text[6:-1]  # Extract text inside \todo{}
            return pf.RawInline(f"<aside>{content}</aside>", format="html")
        if elem.text.startswith(r"\AT{") and elem.text.endswith("}"):
            content = elem.text[4:-1]
            return pf.RawInline(f"<aside class=AT>AT: {content}</aside>", format="html")
        if elem.text.startswith(r"\AS{") and elem.text.endswith("}"):
            content = elem.text[4:-1]
            return pf.RawInline(f"<aside class=AS>AS: {content}</aside>", format="html")

def main():
    pf.run_filter(latex_todo_to_html)

if __name__ == "__main__":
    main()
