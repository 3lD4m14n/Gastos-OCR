import unicodedata


def search_key(value: str) -> str:
    """Forma sin acentos ni mayúsculas para buscar.

    DSQL solo usa la collation C, donde ILIKE y lower() no reconocen la Ñ ni las vocales con
    acento. Por eso la búsqueda compara este valor, calculado en la aplicación.
    """
    decomposed = unicodedata.normalize("NFKD", value)
    return "".join(c for c in decomposed if not unicodedata.combining(c)).casefold().strip()
