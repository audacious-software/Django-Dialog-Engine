
def urls_from_dict(dict_obj):
    urls = []

    for key, value in dict_obj.items(): # pylint: disable=unused-variable
        if isinstance(value, dict):
            child_urls = urls_from_dict(value)

            for url in child_urls:
                if (url in urls) is False:
                    urls.append(url)
        elif isinstance(value, str):
            tokens = value.split()

            for token in tokens:
                if token.lower().startswith('http://') or token.lower().startswith('https://'):
                    if (token in urls) is False:
                        urls.append(token)

    return urls
