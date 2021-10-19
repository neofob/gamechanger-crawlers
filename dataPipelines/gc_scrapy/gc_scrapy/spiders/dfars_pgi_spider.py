import re

from scrapy.http import TextResponse
from scrapy.selector import Selector

from dataPipelines.gc_scrapy.gc_scrapy.GCSpider import GCSpider
from dataPipelines.gc_scrapy.gc_scrapy.items import DocItem

class DoDSpider(GCSpider):
    name = 'dfars_pgi'

    start_urls = ['https://www.acq.osd.mil/dpap/dars/dfarspgi/current/dfars_pgi.html']
    allowed_domains = ['www.acq.osd.mil']

    cac_login_required = False

    def parse(self, response: TextResponse):
        table = response.css('#toctable2')
        rows = table.css('tr')
        prev_num = 'CHAPTER 2'  # ?
        prev_title = 'DEFENSE FEDERAL ACQUISITION REGULATION SUPPLEMENT'
        row: Selector
        for row in rows:
            if row.attrib['class'] == 'rule':
                part_and_title_raw: str = row.css('td:nth-child(1)::text').get()
                if part_and_title_raw is None:
                    part_and_title_raw = row.css('td:nth-child(1) p::text').get()
                part_and_title = self.clean_name(part_and_title_raw)
                part_and_title_split = part_and_title.split(' - ', 1)
                part_num = part_and_title_split[0]
                part_title = part_and_title_split[1] if len(part_and_title_split) > 1 else part_num
                prev_num = part_num
                prev_title = part_title
            else:
                doc_subpart_raw: str = row.css('td:nth-child(1) span::text').get()
                doc_title_raw: str = row.css('td:nth-child(1)::text').get()
                dfars_pdf_href_raw: str = row.css('td:nth-child(3) a::attr(href)').get()
                pgi_pdf_href_raw: str = row.css('td:nth-child(6) a::attr(href)').get()
                
                doc_subpart = self.clean_name(doc_subpart_raw)
                if (doc_subpart in ('TABLE OF CONTENTS', 'COVER PAGE')
                        or (doc_subpart.startswith('PART') and prev_num.startswith('APPENDIX'))):
                    doc_num = f'{prev_num} {doc_subpart}'
                else:
                    prev_num = doc_num = doc_subpart

                doc_title = self.clean_name(doc_title_raw)
                if doc_title.startswith('-'):
                    doc_title = doc_title[2:]
                if doc_title:
                    prev_title = doc_title
                else:
                    doc_title = prev_title

                if 'NO DFARS TEXT' in doc_title_raw or 'NO DFARS TEXT' in prev_title:
                    continue

                # DFARS
                if dfars_pdf_href_raw:
                    dfars_pdf_href = self.ensure_full_href_url(dfars_pdf_href_raw, self.start_urls[0])

                    doc_name = f'DFARS {doc_num} - {doc_title}'

                    version_hash_fields = {
                        "item_currency": dfars_pdf_href.split('/')[-1],
                        "document_title": doc_title,
                        "document_number": doc_num
                    }

                    downloadable_items = [
                        {
                            "doc_type": "pdf",
                            "web_url": dfars_pdf_href,
                            "compression_type": None
                        }
                    ]
                
                    dfars_doc_item = DocItem(
                        doc_type='DFARS',
                        doc_name=doc_name,
                        doc_num=doc_num,
                        doc_title=doc_title,
                        source_page_url=response.url,
                        downloadable_items=downloadable_items,
                        version_hash_raw_data=version_hash_fields,
                    )
                    yield dfars_doc_item

                # PGI
                if pgi_pdf_href_raw:
                    pgi_pdf_href = self.ensure_full_href_url(pgi_pdf_href_raw, self.start_urls[0])

                    doc_num = self.derive_pgi_num(doc_num)

                    doc_name = f'{doc_num} - {doc_title}'

                    version_hash_fields = {
                        "item_currency": pgi_pdf_href.split('/')[-1],
                        "document_title": doc_title,
                        "document_number": doc_num
                    }

                    downloadable_items = [
                        {
                            "doc_type": "pdf",
                            "web_url": pgi_pdf_href,
                            "compression_type": None
                        }
                    ]
                
                    pgi_doc_item = DocItem(
                        doc_type='PGI',
                        doc_name=doc_name,
                        doc_num=doc_num,
                        doc_title=doc_title,
                        source_page_url=response.url,
                        downloadable_items=downloadable_items,
                        version_hash_raw_data=version_hash_fields,
                    )
                    yield pgi_doc_item
                    
    
    def clean_name(self, name):
        return ' '.join(re.sub(r'[^a-zA-Z0-9. ()\\-]', '', self.ascii_clean(name).replace('/', '-')).split())

    def derive_pgi_num(self, dfars_num):
        num_match = re.match(r'[A-Z]+ (?P<num>\d+(?:\.\d+)?)', dfars_num)
        if num_match:
            doc_num = f'PGI {num_match["num"]}'
            return doc_num
        num_match = re.match(r'APPENDIX (?P<num>[A-Z]+(?: PART \d+)?)', dfars_num)
        if num_match:
            doc_num = f'PGI {num_match["num"]}'
            return doc_num
        # ?
        return f'PGI {dfars_num}'
