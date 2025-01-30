# # import re

# # def analyze_xml_tags(file_path):
# #     tag_ranges = []

# #     # Expresiones regulares para tags
# #     opening_tag_pattern = re.compile(r"<(\w+)(\s[^>]*)?>")       # Apertura de tag <tag ...>
# #     closing_tag_pattern = re.compile(r"</(\w+)>")                # Cierre de tag </tag>
# #     self_closing_tag_pattern = re.compile(r"<(\w+)(\s[^>]*)?/>") # Tag self-closing <tag ... />

# #     # Pila para rastrear aperturas de tags normales
# #     open_tags = []

# #     with open(file_path, "r", encoding="utf-8") as file:
# #         lines = file.readlines()

# #     # Analizar línea por línea
# #     for line_num, line in enumerate(lines, start=1):
# #         stripped_line = line.strip()

# #         # Detectar tags self-closing
# #         self_closing_match = self_closing_tag_pattern.match(stripped_line)
# #         if self_closing_match:
# #             tag_name = self_closing_match.group(1)
# #             tag_ranges.append({
# #                 "tag": tag_name,
# #                 "type": "self-closing",
# #                 "start_line": line_num,
# #                 "end_line": line_num,
# #             })
# #             continue

# #         # Detectar apertura de tags normales
# #         opening_match = opening_tag_pattern.match(stripped_line)
# #         if opening_match and not stripped_line.endswith("/>"):
# #             tag_name = opening_match.group(1)
# #             open_tags.append({
# #                 "tag": tag_name,
# #                 "start_line": line_num,
# #             })
# #             continue

# #         # Detectar cierre de tags normales
# #         closing_match = closing_tag_pattern.match(stripped_line)
# #         if closing_match:
# #             tag_name = closing_match.group(1)
# #             # Buscar el tag correspondiente en la pila
# #             for i in range(len(open_tags) - 1, -1, -1):
# #                 if open_tags[i]["tag"] == tag_name:
# #                     tag_ranges.append({
# #                         "tag": tag_name,
# #                         "type": "normal",
# #                         "start_line": open_tags[i]["start_line"],
# #                         "end_line": line_num,
# #                     })
# #                     open_tags.pop(i)
# #                     break

# #     # Revisar posibles tags self-closing multi-línea
# #     multi_line_tag = None
# #     for line_num, line in enumerate(lines, start=1):
# #         stripped_line = line.strip()

# #         if multi_line_tag:
# #             if stripped_line.endswith("/>"):
# #                 multi_line_tag["end_line"] = line_num
# #                 tag_ranges.append(multi_line_tag)
# #                 multi_line_tag = None
# #             continue

# #         # Detectar inicio de tags self-closing multi-línea
# #         if re.match(r"<(\w+)(\s[^>]*)?$", stripped_line) and not stripped_line.endswith("/>"):
# #             tag_name = re.match(r"<(\w+)", stripped_line).group(1)
# #             multi_line_tag = {
# #                 "tag": tag_name,
# #                 "type": "self-closing",
# #                 "start_line": line_num,
# #             }

# #     return tag_ranges


# # # Ejemplo de uso
# # if __name__ == "__main__":
# #     xml_file = "/Users/moylop260/odoo/sbd/sinpe/views/payment_transaction_views.xml"  # Cambia por la ruta de tu archivo XML
# #     tag_data = analyze_xml_tags(xml_file)
    
# #     for tag_info in tag_data:
# #         print(f"Tag: <{tag_info['tag']}>")
# #         print(f"  Tipo: {tag_info['type']}")
# #         print(f"  Línea de inicio: {tag_info['start_line']}")
# #         print(f"  Línea de fin: {tag_info['end_line']}\n")

# import re
# import regex



# xml_regex = regex.compile(r"""
# \s*
# (?:
#   (?P<opentag>
#     <\s*
#     (?P<tagname>\w+)
#     (?P<attribute>
#       \s+
#       (?P<attrname>[^\s>]+)
#       =
#       (?P<attrquote>"|')
#       (?P<attrvalue>[^\s"'>]+)
#       (?P=attrquote)
#     )*
#     \s*
#     (?P<selfclosing>/\s*)?
#     >
#   )
#   (?:
#     (?(selfclosing)|
#       (?P<children>(?R))
#       (?P<closetag><\s*/\s*(?P=tagname)\s*>)
#     )
#   )
# |
#   (?P<text>[^<]*)
# )*
# \s*
# """, flags=re.DOTALL)

# xml_file = "/Users/moylop260/odoo/sbd/sinpe/views/payment_transaction_views.xml"
# with open(xml_file) as xml_obj:
#     xml_content = xml_obj.read()
# import ipdb;ipdb.set_trace()
# xml_regex.search(xml_content)


import regex as re

xml_regex = re.compile(r"""
\s*
(?:
  (?P<opentag>
    <\s*
    (?P<tagname>\w+)                # Nombre del tag
    (?P<attributes>                  # Captura los atributos correctamente
      (?:\s+ 
        (?P<attrname>[\w:-]+)        # Nombre del atributo
        \s*=\s*
        (?P<attrquote>"|')           # Comillas del atributo
        (?P<attrvalue>.*?)           # Valor del atributo (puede estar vacío)
        (?P=attrquote)               # Cierre con la misma comilla
      )*
    )?
    \s*
    (?P<selfclosing>/\s*)?           # Puede ser self-closing
    >
  )
  (?:
    (?(selfclosing)|
      (?P<children>.*?)              # Captura el contenido dentro de la etiqueta
      (?P<closetag>
        <\s*/\s*(?P=tagname)\s*>     # Cierre de la misma etiqueta
      )
    )
  )
|
  (?P<text>[^<]+)                    # Captura texto dentro de las etiquetas
)*
\s*
""", flags=re.DOTALL | re.VERBOSE)

# Leer archivo XML
xml_file = "/Users/moylop260/odoo/sbd/sinpe/views/payment_transaction_views.xml"
with open(xml_file, "r", encoding="utf-8") as xml_obj:
    xml_content = xml_obj.read()

# Buscar coincidencias
matches = xml_regex.finditer(xml_content)

# Imprimir resultados
for match in matches:
    tag_name = match.group("tagname")
    attributes = match.group("attributes")
    is_self_closing = bool(match.group("selfclosing"))
    content = match.group("children") if match.group("children") else ""

    print(f"Tag: <{tag_name}>")
    print(f"  Atributos: {attributes.strip() if attributes else 'Ninguno'}")
    print(f"  Tipo: {'Self-closing' if is_self_closing else 'Normal'}")
    print(f"  Contenido: {content.strip()[:50]}..." if content else "  Sin contenido")
    print("-" * 40)
