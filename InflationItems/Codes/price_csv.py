"""Four-column daily export. Unknown Excel subcategories remain 0."""
import csv
import io
import unicodedata
from decimal import Decimal

FIELDS=['product_name','price','category_number','sub_category_number']
EXCEL_CODES={'raki':211001,'votka':211002,'whisky':211006,'sarap':212101,'bira':213001,
 'sigara':230101,'petrol':711104,'hybrid':711107,'electric':711109,'motorcycle':712001,
 'bicycle':713001,'tyre':721101,'equipment':721201,'accessory':721302,'oil':722401,
 'installation':723001,'maintenance':723002}
def norm(value):
    return ''.join(c for c in unicodedata.normalize('NFKD',value.casefold().replace('ı','i')) if not unicodedata.combining(c))
def classify(row,source,group):
    name=norm(row['product_name'])
    if group==2:
        category=norm(row.get('category',''))
        category={'viski':'whisky','wine':'sarap','beer':'bira','vodka':'votka'}.get(category,category)
        return EXCEL_CODES.get(category,0)
    if source in ('Honda','Mondial'): return EXCEL_CODES['motorcycle']
    if source in ('Decathlon','Salcano'): return EXCEL_CODES['bicycle']
    if source=='Lastikcim':
        parts=[norm(x.strip()) for x in row['product_name'].split('|')]
        key={'lastik':'tyre','motor_yagi':'oil','aksesuar':'accessory','silecek':'equipment'}.get(parts[1] if len(parts)>1 else '')
        return EXCEL_CODES.get(key,0)
    if source=='Euromaster':
        service=name.split(' | ')[-1]
        if 'lastik oteli' in service: return 0
        if any(x in service for x in ['sokme takma','menu 1','menu 2','degisim']): return EXCEL_CODES['installation']
        return EXCEL_CODES['maintenance']
    if source in ('Toyota','Renault','Hyundai'):
        if any(x in name for x in ['hybrid','hibrit',' hev ']): return EXCEL_CODES['hybrid']
        if any(x in name for x in ['elektrik','ioniq','inster']): return EXCEL_CODES['electric']
        if 'eco-g' in name or 'dizel' in name or 'diesel' in name: return 0
        if any(x in name for x in ['t-gdi','tce','turbo tce']): return EXCEL_CODES['petrol']
        if source=='Toyota' and name.startswith('toyota corolla |') and '1.5 ' in name: return EXCEL_CODES['petrol']
    return 0
def convert(raw,source,group,allow_existing_missing_prices=False):
    rows=list(csv.DictReader(io.StringIO(raw)))
    result=[]
    for row in rows:
        if row['price'].strip():
            price=Decimal(row['price'])
            assert price.is_finite() and price>0, row
        else:
            assert allow_existing_missing_prices, row
        name=row['product_name'].strip()
        assert name
        if group==2:
            volume=row.get('volume','').strip()
            if not volume and row.get('volume_ml','').strip(): volume=row['volume_ml']+' ml'
            if volume and norm(volume) not in norm(name): name+=' | '+volume
            for key in ('packaging_type','package_count'):
                if row.get(key,'').strip(): name+=' | '+key+'='+row[key].strip()
        result.append(dict(zip(FIELDS,[name,row['price'],str(group),str(classify(row,source,group))])))
    out=io.StringIO(newline=''); writer=csv.DictWriter(out,FIELDS,lineterminator='\n');writer.writeheader();writer.writerows(result)
    return out.getvalue(),result
