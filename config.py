VALID_PDF_DOMAINS = [
    r"kroll\.com",
    r"cases\.stretto\.com",
    r"dm\.epiq11\.com",
    r"storage\.courtlistener\.com"
]

KROLL_SELECTORS = {
    "search_input": "input[placeholder*='Search'], input[type='search']",
    "case_result": "div.case-result-item, li.search-result",
    "document_table_rows": "//table[contains(@class,'document')]//tr",
    "pdf_links": "//a[contains(@href,'.pdf')]",
    "first_day_fallback": "//a[contains(translate(text(),'ABCDEFGHIJKLMNOPQRSTUVWXYZ','abcdefghijklmnopqrstuvwxyz'),'first day')]"
}

STRETTO_SELECTORS = {
    "document_section": "#documents-section, div.document-list",
    "pdf_links": "//div[@class='document-list']//a[contains(@href,'pdf')]"
}

EPIQ_SELECTORS = {
    "search_input": "input#global-search, input[data-testid='search']",
    "docket_rows": "table.docket-table tbody tr, div.docket-entry"
}

# Add other configurations required for pipeline rules.
EXCLUDED_SET = {
    "Party City",
    "Diebold Nixdorf",
    "Incora",
    "Cano Health",
    "Envision Healthcare"
}
