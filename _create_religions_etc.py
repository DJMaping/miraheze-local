"""Create religion family + denomination pages, a couple of sea stubs, and a
redirect. Registers everything in .state.json so push.py can upload them."""
import json
from pathlib import Path

RELIGIONS = {
    'Kallimethra': ['Therameth', 'Anakalli', 'Doxis', 'Suyuwira', 'Kayamuya'],
    'Kelhari':     ['Oruun', 'Kelhari Veth', 'Thimoruun'],
    'Imarel':      ['Imarel Suun', 'Rhov', 'Tavessi', 'Zovael Karesh', 'Selvaeth', 'Thurvael'],
    'Passanu':     ['Vimanu', 'Passanu Dera', 'Anuthipa'],
    'Tzinalli':    ['Cuetl', 'Omitztli'],
    'Srivandha':   ['Paramaran', 'Bhavandi', 'Karmav Liao'],
    'Thessovai':   [],
}


def family_stub(family: str, variants: list[str]) -> str:
    head = (
        "{{Short description|Religion of Andah}}\n"
        "{{stub}}\n"
        "\n"
        f"'''{family}''' is one of the religions of [[Andah]]."
    )
    if variants:
        head += (
            " Its principal denominations include "
            + ', '.join(f'[[{v}]]' for v in variants[:-1])
            + f' and [[{variants[-1]}]].\n\n'
            + '==Denominations==\n'
            + ''.join(f'* [[{v}]]\n' for v in variants)
        )
    else:
        head += '\n'
    head += '\n==See also==\n* [[Religion in Andah]]\n\n'
    if variants:
        head += f'[[Category:{family}]]\n[[Category:Religions]]\n'
    else:
        head += '[[Category:Religions]]\n'
    return head


def variant_stub(name: str, family: str) -> str:
    return (
        f"{{{{Short description|Denomination of {family}}}}}\n"
        "{{stub}}\n"
        "\n"
        f"'''{name}''' is a denomination of [[{family}]], one of the religions "
        "of [[Andah]].\n"
        "\n"
        "==See also==\n"
        f"* [[{family}]]\n"
        "\n"
        f"[[Category:{family}]]\n"
    )


def family_category_text(family: str) -> str:
    return (
        f"The [[{family}]] religion and its denominations.\n"
        "\n"
        "[[Category:Religions]]\n"
    )


RELIGIONS_CATEGORY_TEXT = (
    "Religions practised on [[Andah]] and their denominations.\n"
)


SEA_STUBS = {
    'Dursio Sea': "The '''Dursio Sea''' is a sea of [[Andah]].",
    'Eashor Sea': "The '''Eashor Sea''' is a sea of [[Andah]].",
}


def sea_stub_text(name: str, body: str) -> str:
    return (
        "{{Short description|Sea on Andah}}\n"
        "{{stub}}\n"
        "\n"
        f"{body}\n"
        "\n"
        "==See also==\n"
        "* [[Andah]]\n"
        "\n"
        "[[Category:Seas]]\n"
    )


REDIRECT_PAGES = {
    'Great Hinsakian Ocean': '#REDIRECT [[Hinsakian Ocean]]\n',
}


def title_to_filename(title: str) -> str:
    return title.replace(' ', '_') + '.wiki'


def main():
    main_dir = Path('pages') / 'Main'
    cat_dir = Path('pages') / 'Category'

    state_path = Path('.state.json')
    state = json.loads(state_path.read_text(encoding='utf-8'))

    created = 0
    skipped = 0

    def write(rel_path: Path, content: str, title: str):
        nonlocal created, skipped
        if rel_path.exists():
            print(f'  SKIP existing: {rel_path}')
            skipped += 1
            return
        rel_path.write_text(content, encoding='utf-8')
        state[title] = {'revid': None, 'path': str(rel_path).replace('/', '\\')}
        print(f'  wrote {rel_path}  (title: {title})')
        created += 1

    # Religion families and variants
    for family, variants in RELIGIONS.items():
        write(main_dir / title_to_filename(family), family_stub(family, variants), family)
        for v in variants:
            write(main_dir / title_to_filename(v), variant_stub(v, family), v)
        if variants:
            write(
                cat_dir / title_to_filename(family),
                family_category_text(family),
                f'Category:{family}',
            )

    # Category:Religions
    write(cat_dir / title_to_filename('Religions'), RELIGIONS_CATEGORY_TEXT, 'Category:Religions')

    # Sea stubs
    for sea_name, body in SEA_STUBS.items():
        write(main_dir / title_to_filename(sea_name), sea_stub_text(sea_name, body), sea_name)

    # Redirects
    for title, content in REDIRECT_PAGES.items():
        write(main_dir / title_to_filename(title), content, title)

    state_path.write_text(json.dumps(state, indent=2, ensure_ascii=False), encoding='utf-8')
    print(f'\n{created} new files; {skipped} skipped.')


if __name__ == '__main__':
    main()
