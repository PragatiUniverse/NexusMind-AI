import json, urllib.parse, urllib.request

def search(query: str, limit: int = 10):
    url = "https://api.openalex.org/works?" + urllib.parse.urlencode({"search": query, "per-page": min(limit, 25)})
    with urllib.request.urlopen(url, timeout=20) as r:
        data = json.load(r)
    def abstract(inv):
        if not inv: return None
        w = sorted((i, k) for k, v in inv.items() for i in v)
        return " ".join(k for _, k in w)
    return [{"openalex_id": x["id"], "title": x.get("title"), "year": x.get("publication_year"), "doi": x.get("doi"),
             "authors": [a["author"]["display_name"] for a in x.get("authorships", [])][:8],
             "abstract": abstract(x.get("abstract_inverted_index"))} for x in data.get("results", [])]
