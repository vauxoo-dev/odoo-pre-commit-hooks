import sys
from lxml import etree
import re


# Cargar el archivo XML
# xml_file = "/Users/moylop260/odoo/sbd/sinpe/views/payment_transaction_views.xml"
xml_file = sys.argv[1]
print(f"XML File {xml_file}")

with open(xml_file, "r", encoding="utf-8") as xml_obj:
    xml_content = xml_obj.read()

parser = etree.XMLParser(remove_comments=True)
tree_node = etree.parse(xml_file, parser=parser)

# Expresión regular mejorada para capturar etiquetas y su contenido
pattern = re.compile(
    r"<(?P<tag>\w+)(?P<attrs>(?:\s+\w+\s*=\s*(?:\"[^\"]*\"|'[^']*'))*\s*)(?P<selfclose>/?)>"
    r"(?P<content>.*?)"
    r"(?:</(?P=tag)>)?",
    re.DOTALL
)

# Función para limpiar atributos
def parse_attributes(attr_string):
    if not attr_string:
        return {}
    attr_pattern = re.findall(r"(\w+)\s*=\s*['\"](.*?)['\"]", attr_string)
    return {key: value for key, value in attr_pattern}

# Buscar coincidencias y mostrar resultados
for num_tag, (match, node) in enumerate(zip(pattern.finditer(xml_content), tree_node.iter()), start=1):
    tag = match.group("tag")
    if node.tag != tag:
        raise UserWarning(f"The tags found from regex are not the same than lxml tree lxml tag {node.tag} vs regex tag {tag}")

    attrs = parse_attributes(match.group("attrs"))
    self_closing = match.group("selfclose") == "/"
    content = match.group("content").strip()

    # Calcular número de línea de inicio
    start_line = xml_content[:match.start()].count("\n") + 1

    # Calcular número de línea de fin correctamente para self-closing y normales
    if self_closing:
        # Considerar que la etiqueta puede ocupar varias líneas
        end_line = start_line + match.group(0).count("\n")
    else:
        # Buscar el tag de cierre
        closing_tag_pattern = re.compile(rf"</{tag}>")
        closing_match = closing_tag_pattern.search(xml_content, match.end())
        if closing_match:
            end_line = xml_content[:closing_match.end()].count("\n") + 1
        else:
            end_line = start_line  # En caso de no encontrar cierre

    print(f"Línea de inicio: {start_line}")
    print(f"Línea de fin: {end_line}")
    print(f"Tag: <{tag}>")
    print(f"  Atributos: {attrs}")
    print(f"  Tipo: {'Self-closing' if self_closing else 'Normal'}")
    # print(f"  Contenido: {content[:50]}..." if content else "  Sin contenido")
    print(f"  sourceline {node.sourceline}")
    print("-" * 40)

    if not start_line <= node.sourceline <= end_line:
        raise UserWarning(f"The tags found from regex have not the same sourceline range than lxml tree lxml sourceline {node.sourceline} vs regex tag {start_line} and {end_line}")
    
    if set(node.attrib) != set(attrs):
        raise UserWarning(f"The attributes found from regex have not the same than lxml tree lxml {node.attrib.keys()} vs {attrs}")



print(num_tag)
tree_node = etree.parse(xml_file)
nodes = [i for i in tree_node.iter()]
print(len(nodes))
