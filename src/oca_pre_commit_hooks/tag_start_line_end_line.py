import sys
from lxml import etree
import re


# Cargar el archivo XML
# xml_file = "/Users/moylop260/odoo/sbd/sinpe/views/payment_transaction_views.xml"
xml_file = sys.argv[1]
print(f"XML File {xml_file}")


# Función para reemplazar comentarios conservando la cantidad de saltos de línea
def preserve_linebreaks(match):
    comment = match.group(0)
    newlines = comment.count("\n")
    return "\n" * newlines  # Reemplaza el comentario por la misma cantidad de saltos de línea


with open(xml_file, "r", encoding="utf-8") as xml_obj:
    xml_content = xml_obj.read()
    # Eliminar comentarios pero conservando la estructura de líneas
    xml_content = re.sub(r"<!--.*?-->", preserve_linebreaks, xml_content, flags=re.DOTALL)

parser = etree.XMLParser(remove_comments=True)
tree_node = etree.parse(xml_file, parser=parser)


# Expresión regular mejorada para capturar etiquetas y su contenido
pattern = re.compile(
    r"<(?P<tag>\w+)"                                      # Nombre del tag
    r"(?P<attrs>(?:\s+\w+\s*=\s*(?:\".*?\"|'.*?'))*\s*)"  # Atributos que pueden ser multilínea
    r"(?P<selfclose>/?)>"                                 # Cierre de etiqueta (self-closing o no)
    r"(?P<content>.*?)"                                   # Contenido interno (si existe)
    r"(?:</(?P=tag)>)?",                                  # Cierre de etiqueta (si no es self-closing)
    re.DOTALL
)

# Función para limpiar atributos
def parse_attributes(attr_string):
    if not attr_string:
        return {}
    attr_pattern = re.findall(r"(\w+)\s*=\s*(['\"])(.*?)(?<!\\)\2", attr_string, re.DOTALL)
    return {key: value for key, _, value in attr_pattern}

# Buscar coincidencias y mostrar resultados
for num_tag, (match, node) in enumerate(zip(pattern.finditer(xml_content), tree_node.iter()), start=1):
    tag = match.group("tag")
    if node.tag != tag:
        import ipdb;ipdb.set_trace()
        raise UserWarning(f"The tags found from regex are not the same than lxml tree lxml tag {node.tag} vs regex tag {tag}")

    attrs = parse_attributes(match.group("attrs"))
    self_closing = match.group("selfclose") == "/"
    content = match.group("content").strip()

    # Calcular número de línea de inicio
    start_line = xml_content[:match.start()].count("\n") + 1

    # Calcular la línea de fin
    if self_closing or not content:
        end_line = start_line + match.group(0).count("\n")
    else:
        # Buscar la etiqueta de cierre, incluso si está en la misma línea
        closing_tag_pattern = re.compile(rf"</{tag}>")
        closing_match = closing_tag_pattern.search(xml_content, match.start())
        if closing_match:
            end_line = xml_content[:closing_match.end()].count("\n") + 1
        else:
            end_line = start_line  # Si no se encuentra cierre

    print(f"Línea de inicio: {start_line}")
    print(f"Línea de fin: {end_line}")
    print(f"Tag: <{tag}>")
    print(f"  Atributos: {attrs}")
    print(f"  Tipo: {'Self-closing' if self_closing else 'Normal'}")
    # print(f"  Contenido: {content[:50]}..." if content else "  Sin contenido")
    print(f"  sourceline {node.sourceline}")
    print("-" * 40)

    if not start_line <= node.sourceline <= end_line:
        import ipdb;ipdb.set_trace()
        raise UserWarning(f"The tags found from regex have not the same sourceline range than lxml tree lxml sourceline {node.sourceline} vs regex tag {start_line} and {end_line}")
    
    if set(node.attrib) != set(attrs):
        import ipdb;ipdb.set_trace()
        raise UserWarning(f"The attributes found from regex have not the same than lxml tree lxml {node.attrib.keys()} vs {attrs}")



print(num_tag)
tree_node = etree.parse(xml_file)
nodes = [i for i in tree_node.iter()]
print(len(nodes))
