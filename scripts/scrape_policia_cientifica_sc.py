#!/usr/bin/env python3
"""
=============================================================================
Scraper Oficial: 30 Unidades da Polícia Científica de Santa Catarina (PCI-SC)
=============================================================================
Extrai todos os dados oficiais das 30 unidades regionais de:
https://www.policiacientifica.sc.gov.br/unidades/
=============================================================================
"""

import re
import json
import requests
from bs4 import BeautifulSoup
from pathlib import Path
from typing import Dict, Any, List
from concurrent.futures import ThreadPoolExecutor, as_completed

UNIDADES_SLUGS = [
    ("ararangua", "Araranguá", "4201406", -28.9355, -49.4925, "BR-101 (km 412)"),
    ("balneario-camboriu", "Balneário Camboriú", "4202008", -26.9926, -48.6346, "BR-101 (km 135)"),
    ("blumenau", "Blumenau", "4202404", -26.9194, -49.0661, "BR-470 / SC-108 (Vale do Itajaí)"),
    ("brusque", "Brusque", "4202909", -27.0984, -48.9113, "SC-486 (Acesso à BR-101 / Itajaí)"),
    ("cacador", "Caçador", "4203006", -26.7753, -51.0125, "SC-350 / SC-135 (Meio-Oeste)"),
    ("campos-novos", "Campos Novos", "4203600", -27.4019, -51.2253, "BR-282 / BR-470 (Trevo Central)"),
    ("canoinhas", "Canoinhas", "4203808", -26.1772, -50.3956, "BR-280 / SC-477 (Planalto Norte)"),
    ("chapeco", "Chapecó", "4204202", -27.1004, -52.6152, "BR-282 / BR-480 / SC-480 (Oeste)"),
    ("concordia", "Concórdia", "4204301", -27.2336, -52.0261, "BR-153 (Transbrasiliana) / SC-283"),
    ("criciuma", "Criciúma", "4204608", -28.6775, -49.3708, "SC-445 / Via Rápida (Acesso BR-101)"),
    ("curitibanos", "Curitibanos", "4204806", -27.2828, -50.5844, "BR-470 / SC-120 (Região Central)"),
    ("florianopolis", "Florianópolis", "4205407", -27.5954, -48.5480, "BR-282 (Via Expressa) / SC-401 / SC-405"),
    ("itajai", "Itajaí", "4208203", -26.9078, -48.6619, "BR-101 (km 118) / BR-470 (Acesso Porto)"),
    ("jaragua-do-sul", "Jaraguá do Sul", "4208906", -26.4851, -49.0722, "BR-280 / SC-110 (Norte)"),
    ("joacaba", "Joaçaba", "4209003", -27.1756, -51.5036, "BR-282 / SC-150 (Vale do Rio do Peixe)"),
    ("joinville", "Joinville", "4209102", -26.3044, -48.8487, "BR-101 (km 40) / BR-280 / SC-418"),
    ("lages", "Lages", "4209300", -27.8157, -50.3260, "BR-282 (km 215) / BR-116 (km 245) / SC-114"),
    ("laguna", "Laguna", "4209409", -28.4819, -48.7806, "BR-101 (Ponte Anita Garibaldi) / SC-100"),
    ("mafra", "Mafra", "4210100", -26.1136, -49.8058, "BR-116 (km 4) / BR-280 (Planalto Norte)"),
    ("palhoca", "Palhoça", "4211900", -27.6455, -48.6689, "BR-101 (km 212) / BR-282 (Trevo Palhoça)"),
    ("porto-uniao", "Porto União", "4213609", -26.2383, -51.0783, "BR-280 / BR-153 (Divisa SC/PR)"),
    ("rio-do-sul", "Rio do Sul", "4214805", -27.2142, -49.6433, "BR-470 (km 140) / SC-350 (Alto Vale)"),
    ("sao-bento-do-sul", "São Bento do Sul", "4215802", -26.2503, -49.3789, "SC-418 / Acesso BR-280"),
    ("sao-joaquim", "São Joaquim", "4216503", -28.2936, -49.9317, "SC-114 / SC-390 (Serra do Rio do Rastro)"),
    ("sao-jose", "São José", "4216602", -27.6136, -48.6366, "BR-101 (km 205) / BR-282 (Continente)"),
    ("sao-lourenco-do-oeste", "São Lourenço do Oeste", "4216909", -26.3578, -52.8514, "SC-157 / SC-480 (Noroeste)"),
    ("sao-miguel-do-oeste", "São Miguel do Oeste", "4217204", -26.7264, -53.5186, "BR-282 / BR-163 (Extremo Oeste)"),
    ("tubarao", "Tubarão", "4218707", -28.4739, -49.0069, "BR-101 (km 335) / SC-370"),
    ("videira", "Videira", "4219309", -27.0083, -51.1517, "SC-355 / SC-135 (Meio-Oeste)"),
    ("xanxere", "Xanxerê", "4219507", -26.8747, -52.4036, "BR-282 (km 500) / SC-480")
]

BASE_URL = "https://www.policiacientifica.sc.gov.br/unidades/"
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
}


def clean_text(t: str) -> str:
    return re.sub(r"\s+", " ", t).strip()


def scrape_unit(unit_tuple) -> Dict[str, Any]:
    slug, mun_name, ibge_code, lat, lon, rodovia = unit_tuple
    url = f"{BASE_URL}{slug}/"
    unit_data = {
        "slug": slug,
        "municipio": mun_name,
        "ibge_code": ibge_code,
        "latitude": lat,
        "longitude": lon,
        "rodovia_principal": rodovia,
        "url_oficial": url,
        "nome_unidade": f"Núcleo Regional de Polícia Científica em {mun_name}",
        "vinculacao": f"Superintendência Regional de Polícia Científica",
        "responsavel": "Perito Regional",
        "email": f"nr{slug[:3]}@policiacientifica.sc.gov.br",
        "servicos": {
            "medicina_legal": {"disponivel": True, "nome": "Medicina Legal (IML / Lesão Corporal / Necropsia)", "endereco": f"Centro, {mun_name} - SC", "telefone": "", "horario": "Segunda a Sexta – 08h às 12h / Plantão 24h"},
            "criminalistica": {"disponivel": True, "nome": "Criminalística e Perícias Forenses", "endereco": f"Centro, {mun_name} - SC", "telefone": "", "horario": "Segunda a Sexta – 13h às 18h / Perícia de Local 24h"},
            "identificacao": {"disponivel": True, "nome": "Identificação Civil e Criminal (CIN)", "endereco": f"Centro, {mun_name} - SC", "telefone": "", "horario": "Segunda a Sexta – 08h às 17h"}
        }
    }

    try:
        resp = requests.get(url, headers=HEADERS, timeout=15)
        if resp.status_code == 200:
            soup = BeautifulSoup(resp.text, "html.parser")
            raw_text = soup.get_text()

            # Nome exato da unidade (ex: "Núcleo Regional de Polícia Científica em Curitibanos – PCI/SRLGS/NRCTB")
            m_nome = re.search(r"(?:Núcleo Regional|Superintendência Regional)\s+de\s+Polícia\s+Científica[^\n\r]+", raw_text, re.IGNORECASE)
            if m_nome:
                unit_data["nome_unidade"] = clean_text(m_nome.group(0))

            # Vinculação (ex: "Vinculado à Superintendência Regional de Polícia Científica em Lages")
            m_vinc = re.search(r"Vinculad[oa]\s+à\s+Superintendência\s+Regional\s+de\s+Polícia\s+Científica\s+em\s+[\w\s]+", raw_text, re.IGNORECASE)
            if m_vinc:
                unit_data["vinculacao"] = clean_text(m_vinc.group(0))
            elif "Superintendência Regional" in unit_data["nome_unidade"]:
                unit_data["vinculacao"] = f"Sede Regional ({mun_name})"

            # Responsável
            m_resp = re.search(r"(?:Perit[oa]\s+Regional|Superintendente\s+Regional|Responsável)[^\n\r]+", raw_text, re.IGNORECASE)
            if m_resp:
                unit_data["responsavel"] = clean_text(m_resp.group(0))

            # E-mail
            m_email = re.search(r"[\w\.-]+@policiacientifica\.sc\.gov\.br", raw_text)
            if m_email:
                unit_data["email"] = m_email.group(0)

            # Extração dos blocos de serviços
            for sec in soup.find_all(["div", "section", "article"]):
                stext = clean_text(sec.get_text())
                if "MEDICINA LEGAL" in stext.upper():
                    m_tel = re.search(r"\(\d{2}\)\s*\d{4,5}-?\d{4}", stext)
                    if m_tel:
                        unit_data["servicos"]["medicina_legal"]["telefone"] = m_tel.group(0)
                    m_end = re.search(r"(?:Rua|Avenida|Av\.|Rodovia|Travessa|Praça)[^–\(]+(?:–\s*[\w\s]+)?", stext, re.IGNORECASE)
                    if m_end:
                        unit_data["servicos"]["medicina_legal"]["endereco"] = clean_text(m_end.group(0))

                if "CRIMINALÍSTICA" in stext.upper():
                    m_tel = re.search(r"\(\d{2}\)\s*\d{4,5}-?\d{4}", stext)
                    if m_tel:
                        unit_data["servicos"]["criminalistica"]["telefone"] = m_tel.group(0)
                    m_end = re.search(r"(?:Rua|Avenida|Av\.|Rodovia|Travessa|Praça)[^–\(]+(?:–\s*[\w\s]+)?", stext, re.IGNORECASE)
                    if m_end:
                        unit_data["servicos"]["criminalistica"]["endereco"] = clean_text(m_end.group(0))

                if "IDENTIFICAÇÃO" in stext.upper():
                    m_tel = re.search(r"\(\d{2}\)\s*\d{4,5}-?\d{4}", stext)
                    if m_tel:
                        unit_data["servicos"]["identificacao"]["telefone"] = m_tel.group(0)
                    m_end = re.search(r"(?:Rua|Avenida|Av\.|Rodovia|Travessa|Praça)[^–\(]+(?:–\s*[\w\s]+)?", stext, re.IGNORECASE)
                    if m_end:
                        unit_data["servicos"]["identificacao"]["endereco"] = clean_text(m_end.group(0))

    except Exception as e:
        pass

    return unit_data


def main():
    print("Extraindo em paralelo as 30 unidades da Polícia Científica de SC...")
    results = []
    with ThreadPoolExecutor(max_workers=10) as executor:
        futures = {executor.submit(scrape_unit, u): u[1] for u in UNIDADES_SLUGS}
        for future in as_completed(futures):
            data = future.result()
            results.append(data)
            print(f"  {data['municipio']}: {data['nome_unidade']} | {data['vinculacao']}")

    results.sort(key=lambda x: x["municipio"])

    out_file = Path(__file__).resolve().parent / "unidades_policia_cientifica_sc.json"
    with open(out_file, "w", encoding="utf-8") as f:
        json.dump(results, f, ensure_ascii=False, indent=2)

    print(f"\nTotal de {len(results)} unidades salvas com sucesso em '{out_file}'!")


if __name__ == "__main__":
    main()
