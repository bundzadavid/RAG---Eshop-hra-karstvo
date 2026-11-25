"""Prevod OWL ontológie na textové dokumenty vhodné pre RAG.

Každá trieda, vlastnosť a individuum (produkt, zákazník, objednávka...)
sa prepíše do krátkeho slovenského textu, ktorý sa potom embeduje.
"""
from collections import defaultdict

from rdflib import BNode, Graph, Literal, URIRef
from rdflib.namespace import OWL, RDF, RDFS


def _local_name(uri) -> str:
    s = str(uri)
    for sep in ("#", "/"):
        if sep in s:
            s = s.rsplit(sep, 1)[1]
    return s


class OntologyText:
    def __init__(self, path):
        self.g = Graph()
        self.g.parse(str(path), format="xml")

    # ---------- pomocné ----------
    def label(self, node) -> str:
        if isinstance(node, Literal):
            return str(node)
        labels = list(self.g.objects(node, RDFS.label))
        sk = [l for l in labels if getattr(l, "language", None) == "sk"]
        if sk or labels:
            return str((sk or labels)[0])
        # individuá často majú vlastnosť "názov"
        for p, o in self.g.predicate_objects(node):
            if isinstance(o, Literal) and _local_name(p) == "názov":
                return str(o)
        return _local_name(node)

    def _fmt_value(self, o) -> str:
        if isinstance(o, Literal):
            v = o.toPython()
            if isinstance(v, bool):
                return "áno" if v else "nie"
            return str(v)
        return self.label(o)

    def _restriction_text(self, r) -> str | None:
        prop = self.g.value(r, OWL.onProperty)
        if prop is None:
            return None
        p = self.label(prop)
        for pred, word in ((OWL.hasValue, "má hodnotu"),
                           (OWL.someValuesFrom, "aspoň jeden z"),
                           (OWL.allValuesFrom, "iba z")):
            val = self.g.value(r, pred)
            if val is not None:
                return f"{p} {word} {self.label(val)}"
        for pred, word in ((OWL.minCardinality, "min."),
                           (OWL.maxCardinality, "max."),
                           (OWL.cardinality, "presne"),
                           (OWL.minQualifiedCardinality, "min."),
                           (OWL.maxQualifiedCardinality, "max."),
                           (OWL.qualifiedCardinality, "presne")):
            val = self.g.value(r, pred)
            if val is not None:
                return f"{p}: {word} {val}"
        return None

    # ---------- typy individuí ----------
    def _domain_index(self):
        idx = {}
        for p, d in self.g.subject_objects(RDFS.domain):
            idx[p] = d
        return idx

    def individual_types(self, ind, domain_idx):
        types = [t for t in self.g.objects(ind, RDF.type) if t != OWL.NamedIndividual]
        if types:
            return types
        # typ nie je uvedený -> odvodíme z domén použitých vlastností
        inferred = {domain_idx[p] for p in self.g.predicates(ind, None) if p in domain_idx}
        return sorted(inferred, key=str)

    # ---------- generovanie dokumentov ----------
    def documents(self):
        g = self.g
        docs = []
        domain_idx = self._domain_index()

        # Spätné vzťahy (napr. ktoré recenzie hodnotia produkt)
        incoming = defaultdict(list)
        for s, p, o in g:
            if isinstance(o, URIRef) and (p, RDF.type, OWL.ObjectProperty) in g:
                incoming[o].append((s, p))

        # Ontológia ako celok
        for ont in g.subjects(RDF.type, OWL.Ontology):
            parts = [f"Ontológia: {self.label(ont)}."]
            for c in g.objects(ont, RDFS.comment):
                parts.append(str(c))
            docs.append(("Ontológia – prehľad", " ".join(parts)))

        # Triedy
        classes = [c for c in g.subjects(RDF.type, OWL.Class) if isinstance(c, URIRef)]
        for c in classes:
            name = self.label(c)
            lines = [f"Trieda (pojem) v ontológii e-shopu s hračkami: {name}."]
            for com in g.objects(c, RDFS.comment):
                lines.append(f"Popis: {com}")
            supers, restr = [], []
            for sc in g.objects(c, RDFS.subClassOf):
                if isinstance(sc, BNode):
                    t = self._restriction_text(sc)
                    if t:
                        restr.append(t)
                else:
                    supers.append(self.label(sc))
            if supers:
                lines.append(f"{name} je podtriedou: {', '.join(supers)}.")
            if restr:
                lines.append("Obmedzenia: " + "; ".join(restr) + ".")
            subs = [self.label(s) for s in g.subjects(RDFS.subClassOf, c) if isinstance(s, URIRef)]
            if subs:
                lines.append(f"Podtriedy: {', '.join(subs)}.")
            props_out = [self.label(p) for p in g.subjects(RDFS.domain, c)]
            if props_out:
                lines.append(f"Vlastnosti triedy {name}: {', '.join(props_out)}.")
            props_in = [f"{self.label(p)} (z {self.label(g.value(p, RDFS.domain))})"
                        for p in g.subjects(RDFS.range, c)]
            if props_in:
                lines.append(f"Na triedu {name} odkazujú vzťahy: {', '.join(props_in)}.")
            members = [self.label(i) for i in g.subjects(RDF.type, c)]
            if members:
                lines.append(f"Príklady (individuá) triedy {name}: {', '.join(members)}.")
            docs.append((f"Ontológia – trieda {name}", "\n".join(lines)))

        # Vlastnosti
        prop_lines = []
        for kind, ptype in (("Vzťah (object property)", OWL.ObjectProperty),
                            ("Atribút (data property)", OWL.DatatypeProperty)):
            for p in g.subjects(RDF.type, ptype):
                d = g.value(p, RDFS.domain)
                r = g.value(p, RDFS.range)
                s = f"{kind} '{self.label(p)}'"
                if d is not None:
                    s += f", doména: {self.label(d)}"
                if r is not None:
                    s += f", rozsah: {self.label(r) if not isinstance(r, URIRef) or 'XMLSchema' not in str(r) else _local_name(r)}"
                prop_lines.append(s + ".")
        # vlastnosti rozdelíme po ~25 riadkov, aby kúsky neboli príliš dlhé
        for i in range(0, len(prop_lines), 25):
            docs.append((f"Ontológia – vlastnosti {i // 25 + 1}",
                         "Vlastnosti v ontológii e-shopu s hračkami:\n" + "\n".join(prop_lines[i:i + 25])))

        # Individuá (konkrétne produkty, zákazníci, objednávky, ...)
        for ind in set(g.subjects(RDF.type, OWL.NamedIndividual)):
            name = self.label(ind)
            types = [self.label(t) for t in self.individual_types(ind, domain_idx)]
            head = f"{name} ({', '.join(types)})" if types else name
            lines = [f"{head} – záznam v e-shope s hračkami."]
            attrs = defaultdict(list)
            for p, o in g.predicate_objects(ind):
                if p == RDF.type:
                    continue
                attrs[self.label(p)].append(self._fmt_value(o))
            for k in sorted(attrs):
                lines.append(f"- {k}: {', '.join(attrs[k])}")
            for s, p in incoming.get(ind, []):
                lines.append(f"- {self.label(s)} → {self.label(p)} → {name}")
            docs.append((f"Ontológia – {name}", "\n".join(lines)))

        return docs


def load_ontology_documents(path):
    """Vráti zoznam (titulok, text)."""
    return OntologyText(path).documents()


if __name__ == "__main__":
    import sys
    from config import ONTOLOGY_FILE

    sys.stdout.reconfigure(encoding="utf-8")
    docs = load_ontology_documents(ONTOLOGY_FILE)
    print(f"{len(docs)} dokumentov z ontológie\n")
    for title, text in docs[:3] + docs[-3:]:
        print(f"=== {title} ===\n{text}\n")
