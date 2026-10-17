# Rules for coicop.codes(). Each rule is
#   (code, name regex, category regex, unless regex, stores, note)
# Regexes run on normalized text: lower case, Turkish letters folded to ASCII
# (ç→c, ğ→g, ı→i, ö→o, ş→s, ü→u), punctuation turned into single spaces.
# Turkish stems change before suffixes (koltuk/koltuğu, dolap/dolabı), hence
# patterns like koltu[kg] and dola[pb]. The first matching rule wins; code
# "0" means the basket has no item for that product type.

# Product types without a basket item of their own. Decided with Batu on
# 2026-10-17; the reasoning is in the mapping guide.
LIGHTING = "0552203"          # lamps and fittings go with light bulbs
DECOR = "0"                   # vases, frames, mirrors: only item in 05114 is carpet
STORAGE = "0540301"           # boxes, baskets, hangers: household utensils
BATH_ACCESSORIES = "0431108"  # soap dishes, towel rails: fitted with plumbing
FITTINGS = "0431109"          # COICOP 04.3.1 lists door fittings, sockets, wiring
TOOLS = "0"                   # COICOP 05.5.1 and 05.5.2.1 have no basket item
GARDEN = "0"                  # plants, pots, garden tools: no basket item
WORK_SAFETY = "0"
GARDEN_CHAIR = "0511105"
GARDEN_TABLE = "0511102"
GARDEN_SEATING = "0511116"
KITCHEN_CABINETS = "0511102"
BATHROBE = "0521307"

CONSTRUCTION = ("AfeksYapiMarket,Bauhaus,Ereyon,FiltasYapi,HanCivata,Hausmart,Koctas,LoyaMakina,"
                "Nalburadam,Nalburcuk,Nalburtek,SanatYapiOnline,TasciYapiMarket,Yapıyoz,yapimaks")

GLASS = r"^(?=.*\b(cam|borosilikat|kristal|camdan)\b)(?=.*\b(taba[kg]|kase|barda[kg]|surahi|sekerli[kg]|cerezli[kg]|gondol|saklama|kavanoz|yagli[kg]|tepsi|sunumlu[kg]|kupa|fincan|servis|firin kab|caydanli[kg]|demli[kg]|karaf|soslu[kg]|tatlili[kg]|kek|pasta|kayik|baharat|yag|sise|meyveli[kg]|salata|su takim|takimi|seti|fanus))"

RULES = [
    # --- Store specific -----------------------------------------------------
    ("0533001", r"tamir|servis|bakim", "", "", "Armut", "appliance repair"),
    ("0562902", r"ev temizli|temizlikci|gundelikci", "", "", "Armut", "house cleaning"),
    ("0562901", r"yikama", "", "", "Armut", "carpet and sofa cleaning"),
    ("0532901", "", r"utu grubu", "", "LoyaMakina", "iron parts and ironing systems"),
    (KITCHEN_CABINETS, r"\w", r"mutfak mobilya|mutfak tezgah|mutfak dolap|\bmetod\b", r"sandalye|tabure|masa\b|masasi", "Ikea", "Ikea kitchen furniture category"),
    ("0511108", r"\w", r"gardirop|oda ayirici|skytta", r"cocuk", "Ikea", "Ikea wardrobe category"),
    ("0511116", r"\w", r"\bbesta\b|tv ve medya|depolama sistemleri", r"kutu|sepet|saklama|lamba|aydinlatma", "Ikea", "Ikea living room storage category"),
    ("0431108", r"\w", r"banyo dolap|banyo mobilya|lavabo dolap", "", "Ikea", "Ikea bathroom furniture category"),
    ("0511108", r"surgu kapak|gomme dolap|rayli cekmece|\bpax\b|komplement", "", "", "Ikea", "Ikea wardrobe parts"),
    (KITCHEN_CABINETS, r"\bkapak\b|kaplama paneli|\btezgah\b|mutfak cekmecesi|arka panel|\bmetod\b|maximera", r"mutfak", "", "Ikea", "Ikea kitchen fronts and worktops"),
    ("0511116", r"\bbesta\b|\beket\b|\bkallax\b|\bbilly\b|iskelet|\braf\b|ust panel|paravan", "", r"banyo|mutfak", "Ikea", "Ikea living room storage parts"),
    # MediaMarkt and Vestel list appliances under plain slugs; model names carry words like "Puzzle".
    ("0531101", r"\w", r"buzdolabi", "", "MediaMarkt,Vestel", "fridge category"),
    ("0531103", r"\w", r"derin dondurucu", "", "MediaMarkt,Vestel", "freezer category"),
    ("0531201", r"\w", r"camasir makine", "", "MediaMarkt,Vestel", "washing machine category"),
    ("0531202", r"\w", r"kurutma makine", "", "MediaMarkt,Vestel", "dryer category"),
    ("0531106", r"\w", r"bulasik makine", "", "MediaMarkt,Vestel", "dishwasher category"),
    ("0531301", r"\w", r"klima", "", "MediaMarkt,Vestel", "air conditioner category"),
    ("0531303", r"\w", r"isitici", "", "MediaMarkt,Vestel", "heater category"),
    ("0531108", r"\w", r"firin|ocak", "", "MediaMarkt,Vestel", "oven and hob category"),
    ("0552201", r"\bpil\b|pili\b|piller\b|alkalin", r"piller", "", "MediaMarkt", "battery category"),

    # --- Tools and fittings whose names share words with other products -----
    (FITTINGS, r"anahtar|cerceve|\btapa\b|priz|buat|kablo|sigorta|dimmer", r"elektr|aydinlatma",
               r"lokma|allen|kombine|yildiz|iki agiz|torx|alyan|kontrol kalem|tornavida|pense|anahtar (takimi|seti)|network|ethernet|rj45|hdmi|\bvga\b|\busb\b|sarj",
               "", "electrical fittings by category"),
    (LIGHTING, r"sapka|sapkasi|kulah", r"aydinlatma|abajur|avize|lambader", "", "", "lamp shades by category"),
    ("0974009", r"kalem zimparasi", "", "", "", "pencil sanding pads"),
    (TOOLS, r"odun .*kancasi|zimba (makinesi|tabancasi)|zimba teli sokucu", "", "", CONSTRUCTION, "tools named like other goods"),
    (FITTINGS, r"zimba teli", "", "", CONSTRUCTION, "staples in hardware stores"),
    ("0974004", r"cadence|ponart|\brich\b|varak|yaldiz|stencil|chalk|akrilik|keten yagi|\d+ ?cc\b|\bfirca\b", r"dekorasyon ve ev",
                r"bardak|kupa|saklama|tabak|\d+ ?(l|lt|litre)\b", "Bauhaus", "Bauhaus hobby and art supplies"),
    ("0974005", r"canvas pad|painting blok|drawing|resim (blok|defter)|eskiz", "", r"zimpara", "", "drawing pads"),
    (TOOLS, r"matkap|vidalama|tornavida|\bpense\b|pensesi|pensi\b|kargaburun|yan keski|\bkeski\b|cekic|testere|taslama|zimpara|iskarpela|su terazisi|serit metre"
            r"|lazer (metre|olcer|terazi|cizgi|hizalama|uzaklik)|\bkumpas|mengene|isken[cs]e|kiskac|havya|lehim|freze|planya|dekupaj|\bkirici\b|perforator|kompresor"
            r"|kaynak (makine|maske|elektrot|teli|pense)|elektrot|takim (cantasi|arabasi)|alet (cantasi|seti|takimi)|lokma|\bbits\b"
            r"|(matkap|vidalama|delme|freze|panc|karot|bits|tornavida|kesme|zimpara|taslama) (ucu|uclari|uc)\b|(kesici|kesme|elmas|zimpara|taslama|flap|fiber|polisaj|yuzey temizleme) disk"
            r"|tel firca|maket bica[kg]|\bdremel|ceta form|knipex|izeltas|(lokma|allen|kombine|yildiz|iki agiz|acik agiz|boru|ayarli|kurbagacik|tork|bijon|cirtli|circir|alyan) anahtar"
            r"|anahtar (takimi|seti)|olcum (cihazi|aleti)|multimetre|pens ampermetre|akulu (matkap|vidalama|taslama|testere|darbeli|somun|kirici|polisaj|zimpara|cam temizle)"
            r"|darbeli|somun sikma|yedek aku|sicaklik olcum|karistirici \d+ ?w|\d+ ?w .*karistirici|elektrikli .*karistirici"
            r"|starter kit|aku (seti|paketi|sarj)|\b(10 8|12|14 4|18|20|36|40) ?v\b.*\baku\b|\baku\b.*\b(10 8|12|14 4|18|20|36|40) ?v\b"
            r"|jenerator|\bvinc\b|irgat|caraskal|balta\b|baltasi|kerpeten|metresi|rulman|isaretleme|malasi|mala (no|kpl|\d)|kaynak makina|avuc rende|ahsap rende"
            r"|cam elmas|traslama|ufleme makine|\d+ ?w\b.*(makine|testere|taslama|matkap|freze)|seramik .*vantuz|titresimli vantuz"
            r"|\bgba\b|\d+ ?v .*batarya|batarya \d+ \d+ ?ah|\d+ \d+ ?ah .*batarya", "",
            r"\bet cekic|ekmek testere|(buz|ceviz|fistik|findik) kirici|sarimsak|tirnak|(yemek|cay|kahve|nevresim|kahvalti|servis) takimi|uclu vida"
            r"|buzdolab|buz dolab|aku bakim|desulf|hamur karistirici", "", "tools and tool accessories"),
    (TOOLS, r"\bpanc\b|panci\b|takim canta|alet canta|boya tabanca|boya (ve harc )?(karistirici|mikser)|harc (karistirici|mikser)|tabancasi\b", "", r"masaj|sicak hava", "", "tool bags, punches, spray guns"),
    (GARDEN, r"tohum|\bfide|fidesi|gubre|\btorf\b|bitki topra|cicek topra|saksi topra", "", "", "", "seeds, soil, fertiliser"),
    (TOOLS, "", r"anahtarlar|tornavida|matkap|uclari|\bucu\b|pense|keski|zimpara|testere|egeler|torpu|iskarpela|isken|cekic|kargaburun|yankeski|takim canta|terazi"
                r"|metreler|kumpas|lokma|panclar|freze|havsa|kesme siyirma|cektirme|segman|balta|taslama|vidalama|kirici|delici|kaynak makine|olcu|olcum",
     r"priz|elektrik|aydinlatma|vida (ve|civata)|civata", "", "tool categories"),
    (FITTINGS, r"raf (pimi|konsol|konsolu|destegi|tasiyici|alti konsol|braketi)|kapi (rozeti|kolu|kilidi|hidroligi|yayi|stoperi|tamponu|mentesesi)|\bmentese|mentesesi"
               r"|cekmece rayi|teleskopik ray|ray makarasi|\bdubel\b|dubeli\b|\bvida\b|vidasi\b|vidalar\b|civata|\bsomun\b|percin|kelepce|kosebent|mobilya (kulpu|ayagi|tekerlegi)"
               r"|\bkulp\b|kulpu\b|kulbu\b|baza pabuc|kapi rozet|aski borusu|askidubel|dubel|cekmece (bordur|rayi|sistem|mekanizma)|bordur|minifix|\btij\b"
               r"|klima kanali|kanal tapa|menfez|agraf|carpma|mavzer|\bsurgu (sac|kilit)|baglanti (sac|lama)|lama baglanti|sac gonye|kangal boru|koruge|spiral boru"
               r"|aspirator borusu|davlumbaz borusu|(pencere|kapi) bandi|sunger bant|kapi alti (fircasi|bandi|fitili|ruzgarlik)|kapi fitil|\bfitil\b|fitili\b|reze\b|rezesi|kapi (stobu|otomatig)"
               r"|baglanti gonyesi|kose gonyesi|kose koruyucu|kaydirmaz bant|komitator|wd ?40|\bgres\b|yag sprey|pas sokucu|yaglayici sprey|bakim spreyi",
               "", r"klozet", "", "fittings named plainly"),
    ("0431108", r"kuresel (vana|van)|kaplin|reduksiyon|\bte (gecme|dis|ic)|\bkalde\b|flator|su deposu|dus kanali|mix kartus|batarya kartus|aksesuar seti banyo|banyo .*aksesuar"
                r"|wc matik|dus basligi|lamineli baslik|sampuanlik|dis fircasi (askisi|tutucu|standi)|tiras bicagi tutucu|tuvalet kagidi (verici|dispans|stand)|kagit verici",
                "", "", "", "plumbing and bath accessories named plainly"),
    ("0431109", r"alcisi|\bbitu|shingle|dolomit|agrega|aderans|\blateks\b.*(katki|su gecirmez)|su gecirmez(lik)? katki|folyo bant", "", "", "", "building materials named plainly"),
    ("0431102", r"yapiskanli folyo|d c fix|dekor folyo", "", "", "", "self-adhesive wall and furniture film"),
    ("0721302", r"autokit", "", "", "", "car care brand"),
    ("0540104", r"kahvaltilik|matcha", "", "", "", "breakfast and tea sets"),
    ("0540301", r"masrapa|tabaklik|bulasik altligi|dilimleyici|folyoluk|deterjanlik|\btandem\b|midi set|\bhavan\b|pasta hazirlik|baski pul|sut potu|\bpot\b"
                r"|badya|\bkova\b|kovasi|huni|posetlik|fresh box|ocak koruyucu|saklama (seti|kutu)|tasima kolisi|\bkoli\b"
                r"|beslenme|ogle yemegi kutusu|lunch box|yemek kutusu|sise kapatici|sise tipasi|makarna kasig|tel cirpici|cirpma teli|tava sapi|sap tutacag"
                r"|\bolcek\b|dondurma kalibi|bulasik mati|(servis|kahvalti|sunum) tahtasi|damgasi|damga seti|vakumlu poset|vakum poseti|damacana pompasi"
                r"|kesme tablasi|bbq aleti|mangal aleti|(bambu|ahsap) .*(sunumluk|servis tabag|kesme)|narenciye sikacag|deterjan (saklama )?kab|(avokado|sebze|meyve) aleti",
                "", r"elektrikli|sarjli|\d+ ?w\b|tabagi\b|tabaklari|onlug|onluk", "", "kitchen articles named plainly"),
    ("0521208", r"complete set|yatak seti", "", r"baza|baslik|karyola", "", "bed linen sets"),
    ("0531401", r"(dreame|roborock|xiaomi|roomba|ecovacs) .*(firca|filtre|mop|pad|torba)", "", "", "", "robot vacuum parts"),
    ("0431108", r"aritici|\baritma", "", "", "", "water filters"),
    ("0531306", r"havlupan|aluminyum radyator|\bradyator\b", "", r"vana|tapa|temizle|firca|yagli|elektrik|isitici|oto|arac", "", "radiators"),
    ("0431109", r"ahsap (raf|levha|tahta|panel)|ebatli ahsap|kenar band|yonga levha|\btahta\b|cita(si)?\b|melamin levha|seperator", r"mobilya|yapi|insaat|ahsap|kereste",
                "", "", "wood boards and trims"),
    ("0511116", r"dilsiz usak|\busak\b", "", "", "", "valet stands"),
    ("0521101", r"kugel|rustik (ucu|uc|bas)", "", "", "", "curtain rod ends"),
    ("0511102", r"mutfak tezgahi|tezgah alti unite|kiler", "", "", "", "kitchen units named plainly"),
    ("0521905", r"musamba", "", "", "", "oilcloth"),
    (GARDEN, r"panel cit|cit (kapak|direk|paneli)|su zamanlayici|sulama", "", "", "", "garden named plainly"),
    (FITTINGS, r"\bpriz|prizi|grup priz|uzatma kablo|anahtar (modul|priz|kapak|cerceve)|vavien|komutator|permutator|(ikili|uclu|tekli|dortlu|besli|yatay|dikey) cerceve"
               r"|isikli anahtar|kacak akim|\bsigorta|klemens|\bbuat\b|kablo kanali|kapi zili|dimmer|piriz", "",
               r"saatli priz|zamanlayici", "", "electrical fittings named plainly"),

    # --- Pets (09) ----------------------------------------------------------
    ("0932201", r"\b(kedi|kopek|kus|balik|kemirgen|hamster|tavsan|evcil)\b.*\b(mama|mamasi|yem|yemi|odul|konserve)\b"
                r"|\b(mama|yem|odul)\b.*\b(kedi|kopek|kus|balik)\b", "", r"mama (sandalye|onlu|mati|kabi|kasesi)|bebek|kabi\b|kasesi|standli|hazneli", "", "pet food"),
    ("0932204", r"(kedi|kopek|evcil|tasma|akvaryum|kemirgen|hamster|harness|leash)|kus (kafes|yemligi|yuvasi)|kedi kumu|tirmalama"
                r"|\bpet (fircasi|yatagi|minderi|kapisi|tasima|oyuncag|mama|su kab|kafes|aksesuar)", "",
                r"kedi goz|kedi dili|sifon|tasma (parcasi|borusu)|lavabo|kuvet|desenli|baskili", "", "pet products"),
    ("0932204", "", r"evcil hayvan|petshop|pet shop", "", "", "pet category"),

    # --- Toys, festive, hobby (09) -----------------------------------------
    ("0921207", r"akulu (cocuk )?(araba|motor|jeep|atv)|pedalli (araba|traktor)|denge bisiklet|cocuk scooter|\bscooter\b", "",
                r"elektrikli scooter|yetiskin|tirpan|\bcim\b|kenar kesme|teker|branda|kilif|ortu", "", "ride-on toys"),
    ("0921104", r"oyun konsol|playstation|xbox|nintendo|atari", "", r"koltu[kg]|sandalye|baskili|desenli|kupa|bardak|tabak", "", "game consoles"),
    ("0921204", r"oyuncak|pelus (oyuncak|ayi|tavsan|kopek|kedi|bebek)|uyku arkadasi|\blego\b|puzzle|yapboz|oyun (cadiri|hamuru|seti|mati|makinesi)|bebek evi|kaydirak|cocuk salincag"
                r"|yilbasi (agaci|susu|suslemesi|topu|yildizi|sus|elfi|figur)|(cam|noel) agaci|ren geyigi|agac susu|celenk|noel baba|kar kuresi|parti (susu|seti|balonu)|\bbalon\b"
                r"|model (araba|arac|ucak)|diecast|satranc|tavla\b|tavlasi|okey takimi|zeka oyunu|kutu oyunu|muzik kutusu|su topu|ziplayan top|sisme havuz|cocuk havuzu", "",
                r"oyuncak (sepeti|dolabi|kutusu|duzenleyici|rafi|sandig|organizer)|yilbasi isik|isik zinciri|buzdolabi|no frost|home puzzle|profil|ortusu"
                r"|kirlent|yastik|battaniye|ortu|terlik|tabak|tabagi|kase|kupa|bardak|fincan|tepsi|havlu|nevresim", "", "toys and festive decorations"),
    ("0974004", r"hobi boya|resim boya|akrilik (hobi|resim)|sulu boya|guaj|yagli boya (tup|seti|resim)|\btuval\b|ebru|ahsap boyama"
                r"|cam boyasi|seramik boyasi|kumas boyasi|hobi vernik|art vernik|multi ?surface|hybrid akrilik|akrilik \d+ ml|\d+ ml akrilik"
                r"|\brich (akrilik|multi|kumas|selfy|metalik|cam|ahsap)|akrilik boya \d+ cc",
                "", r"mastik", "", "art and hobby paints"),
    ("0974004", "", r"hobi boya", "", "", "hobby paint category"),
    ("0431102", "", r"seramik ve porselen", "", "FiltasYapi", "Filtas tile category"),
    ("0431108", "", r"vitrifiye|armatur|aksesuar", "", "FiltasYapi", "Filtas sanitary categories"),
    ("0721201", r"romork (fisi|kaplini|tekeri|lambasi|soketi)|karavan (kaplini|fisi)", "", "", "", "trailer parts"),

    # --- Sports and camping (09) -------------------------------------------
    ("0452201", r"(kamp|piknik) (tupu|gazi)|gaz kartus|kartus gaz|butan gaz|\blpg\b|tup gaz", "", r"regulator|dedektor|hortum|torch|purmuz(?!.*kartus)", "", "bottled gas"),
    ("0922102", r"jimnastik|kosu bandi|kondisyon bisiklet|eliptik|spin bisiklet|agirlik (sehpasi|plakasi|seti|istasyonu)|dambil|halter|kettlebell"
                r"|direnc (bandi|lastigi)|pilates|yoga (mati|minderi|bloku)|egzersiz (mati|bandi|aleti|topu)|fitness|barfiks|step tahtasi|atlama ipi"
                r"|vibration plate|titresimli (spor|platform)",
                "", r"havlu|canta", "", "home fitness"),
    ("0922103", r"kamp (sandalye|tabure|masa|cadir|mat|yatag|yastig|ocag|lamba|fener|seti|mutfa|tencere|canta|sobasi|battaniye)"
                r"|\bcadir|uyku tulumu|sisme (yatak|bot|havuz|sezlong|deniz|simit|kano)|deniz (yatagi|simidi|gozlugu)|\bhavuz\b"
                r"|\bolta\b|balikci|\bav (bicagi|malzeme)|\bcaki\b|cakisi|futbol topu|basketbol|voleybol|tenis|badminton|bilardo"
                r"|\bdart\b|kaykay|\bpaten\b|snorkel|termal canta|termo canta|buzluk|soguk tutucu|sogutucu canta|piknik (cantasi|sepeti|seti|masasi|ortusu)"
                r"|can yelegi|trekking", "", r"tirpan", "", "sports and camping"),

    # --- Vehicles (07) ------------------------------------------------------
    ("0721302", r"bisiklet (kilidi|pompasi|lambasi|zili|sepeti|kaski|tasiyici|askisi|selesi|aksesuar)|bisiklet .*pompasi", "", "", "", "bicycle accessories"),
    ("0713001", r"\bbisiklet\b|bisikleti\b|\bbmx\b", "", r"kondisyon|spin|egzersiz|denge|yaka|anahtar|yikama|saat|fener|pompa|sisirme", "", "bicycle"),
    ("0722401", r"motor yag|sanziman yag|antifriz|fren (hidrolik|yagi)|yag katkisi|yakit katkisi|enjektor temizleyici|(performans|benzin) .*iyilestirici", "",
                r"zincir yagi|test|olcer|cihaz", "", "lubricants and fluids"),
    ("0721101", r"(oto|arac|araba|otomobil) (lastik|jant)|kis lastigi|yaz lastigi", "", r"zincir|paspas|tamir|onarim|boya|yikama", "", "tyres"),
    ("0721201", r"silecek|silecegi|(oto|arac|araba) (ampul|far|filtre|balata|yedek parca|kornasi|sigorta)|\bbuji|hava filtresi|yag filtresi|polen filtresi"
                r"|arac akusu|oto akusu|\baku \d{2,3} ?ah|\d{2,3} ?ah aku|\d+ \d+ v a\b|lastik (tamir|onarim)", "",
                r"\bcam sil|banyo|dus|pencere|ev tipi|seramik|kazima|sapli|anahtar", "", "vehicle parts"),
    ("0721302", r"(oto|arac|araba|otomobil) (aksesuar|paspas|koltuk|kilif|koku|parfum|sampuan|cila|bakim|temizle|vakum|supurge|sarj|tutucu"
                r"|bagaj|organizer|gunes|perde|branda|ici|kamera|cop kutu|boya|rotus|pasta|wax|cekme|yikama)|\boto\b.*\b(koku|parfum|sprey)\b"
                r"|bagaj organizer|portbagaj|tavan bagaj|lastik zinciri|kar zinciri|patinaj zinciri|cekme (halati|kancasi)|takviye kablosu|aku takviye"
                r"|ikaz (ucgeni|yelegi)|ilk yardim (cantasi|seti)|cam suyu|aku (sarj|bakim)|motosiklet (brandasi|ortusu|kilifi)|motor kilifi|arac ustu"
                r"|lastik (hava )?basinc|lastik (sisirme|hava) pompasi", "", r"cardak|jant", "", "vehicle accessories"),

    # --- Information and communication (08) --------------------------------
    ("0819201", r"tv (aski|askisi|duvar aparat|standi)|(telefon|tablet|usb|type c|lightning|iphone|samsung|kablosuz) (sarj|kilif|tutucu|stand)|(usb|type c|lightning|iphone|samsung|sarj) kablo"
                r"|sarj (kablosu|adaptoru)|powerbank|power bank|ekran koruyucu|\bhdmi\b|uydu (alici|cihaz)|\banten\b|\bmodem\b|\busb\b|airpods"
                r"|laptop kilif|macbook|kulaklik kilif|laptop (destegi|standi|stant)|notebook (stand|stant)|network kablo|ethernet kablo|\bvga\b", "",
                r"\baku\b|akulu|\d+ ?v\b|matkap|priz|\bfan\b|\bpil\b|piller|alkalin|\bled\b|lamba|lambasi|fener|isik", "", "ICT accessories"),

    ("0814007", r"televizyon|\b(smart|led|qled|oled|uhd|4k) tv\b|\d+ (inc|ekran) (tv|televizyon)", "",
                r"(tv|televizyon) (unite|sehpa|dolab|aski|duvar|stand|kumanda|kablo)", "", "television"),
    ("0814001", r"hoparlor|soundbar|ses sistemi|\bradyo\b|muzik seti|kulaklik|\bpikap\b|plak calar|projeksiyon cihaz|bebek telsiz|\btelsiz\b|mikrofon",
                "", r"is guvenlik|kulak koruyucu|antifon|baret|\bpil\b|pili\b", "", "audio and video"),
    ("0813209", r"\bmouse\b|klavye|yazici|\btoner\b|(yazici|murekkep) kartus|webcam|harici disk|flash (bellek|disk)|laptop sogutucu|\bmonitor\b",
                "", r"bebek monitor|mickey|minnie|baski|desen|masa|masasi|ayagi|kablo", "", "computer peripherals"),
    ("0819201", r"(laptop|notebook) .*(stant|standi|destegi)", "", "", "", "laptop stands"),
    ("0813101", r"dizustu bilgisayar|\blaptop\b|masaustu bilgisayar|tablet bilgisayar|\bipad\b", "", r"canta|stand|sogutucu|masa|sehpa|kilif|destek|kasa", "", "computers"),
    ("0819103", r"akilli (saat|bileklik)", "", "", "", "other communication devices"),

    # --- Personal care and effects (13) ------------------------------------
    ("1311103", r"sac (kurutma|duzlestirici|duzlestirme|masasi|sekillendirici|kurutucu)|fon makinesi|bigudi|sicak hava (fircasi|tarag)|airwrap",
                "", r"sac kurutma (havlusu|bonesi)", "", "electric hair care"),
    ("1311101", r"tiras makine|sakal (kesme|duzeltme)|\btrimmer\b|erkek bakim seti|multigroom", "", r"\bcim\b|\bcit\b|bahce|kenar", "", "electric shaver"),
    ("0613318", r"sicak su torbasi|ates olcer|vucut sicakligi|(kizilotesi|temassiz) (isi|ates) olcer|isi olcer", "", r"mutfak|firin|yemek|ortam", "", "health aids for daily life"),
    ("1311104", r"epilator|epilasyon|agda (makinesi|isitici)|elektrikli dis fircasi|dis fircasi (elektrikli|sarjli|sonik)|agiz dusu"
                r"|masaj (aleti|tabancasi|yastigi|koltugu|cihazi|minderi)|yuz temizleme (cihaz|fircasi)|manikur|pedikur (seti|makinesi)"
                r"|vucut (tartisi|analiz)|banyo tartisi|baskul|tansiyon aleti|therabody", "",
                r"mutfak|vinc|kantar|asma|el kantari|masa", "", "other personal care appliances"),
    ("1312026", r"tuvalet kagidi", "", r"kagitli|aparat|stand|tutucu|askisi|hazne|dispens|dispans|verici", "", "toilet paper"),
    ("0561198", r"yuzey temizlik (havlusu|mendili)|temizlik (havlusu|mendili)|islak (yuzey|mobilya|cam|banyo|mutfak|temizlik) (havlu|mendil)"
                r"|(ahsap|deri|mobilya) (bakim|temizlik) mendili|temizleme mendili", "", "", "", "surface wipes"),
    ("1312027", r"kagit mendil|cep mendil|islak mendil|islak havlu|\bmendil\b", "",
                r"yuzey|temizlik|mutfak|\bcam\b|mobilya|mendil (kutusu|lik)|mendillik|leke", "", "other paper products"),
    ("1312017", r"sivi sabun|(el|mutfak) sabunu|sabunu sivi|el yikama (jeli|sivisi)|kopuk sabun", "",
                r"dispenser|sabunluk|sabunlugu|pompa|hazne|aparat|kabi|sisesi|otomatik", "", "hand soap"),
    ("1312018", r"kati sabun|banyo sabunu|dus (jeli|kremi|kopugu)|\bsabun\b", "",
                r"sabunluk|sabunlugu|dispenser|pompa|aparat|hazne|kabi|otomatik|sabun (tabagi|standi)|arap sabunu|sabun tozu|temizleyici|yuzey|kokulu|kese", "", "bath soap"),
    ("1312025", r"sampuan|sac (kremi|bakim|maskesi|spreyi|boyasi|yagi|serumu|fircasi|tokasi)|\btarak\b|\btoka\b", "",
                r"\bhali\b|koltuk|\boto\b|arac|kopek|kedi|evcil|\bcim\b|sampuanlik|pafta|kafasi|tesisat|\baks\b|kaplama|cubuk", "", "hair care products"),
    ("1312016", r"dis macunu", "", "", "", "toothpaste"),
    ("1312002", r"dis fircasi", "", r"elektrikli|sarjli|sonik|fircalik|fircaligi|tutucu|bardagi|standi|kabi|aski", "", "toothbrush"),
    ("1312019", r"parfum|\bedp\b|\bedt\b|eau de (parfum|toilette|cologne)|body mist", "",
                r"\boda\b|ev parfumu|\boto\b|arac|camasir|kumas|tekstil|\bhali\b|dolap|ortam|cubuklu|sisesi|dekoratif|zimba|makine", "", "perfume"),
    ("1312020", r"deodorant|roll on|antiperspirant", "", "", "", "deodorant"),
    ("1312021", r"kolonya", "", r"kolonyalik|kolonya (sise|kabi)", "", "cologne"),
    ("1312023", r"\bruj\b(?! pembe)|maskara|fondoten|\boje\b|allik|far paleti|eyeliner|concealer", "", r"tablo|organizer|organizeri", "", "cosmetics"),
    ("1312024", r"gunes (kremi|losyonu)|\bspf\b", "", "", "", "sunscreen"),
    ("1312001", r"jilet|tiras bicagi|kartuslu tiras", "",
                r"freze|planya|ahsap|marangoz|\d+ ?mm\b|bicak|bileme|kazima|hamur|jiletli|tutucu|aski", "", "razor blades"),
    ("1312030", r"hijyenik ped|kadin pedi|gunluk ped", "", "", "", "sanitary pads"),
    ("1312022", r"vucut (losyonu|kremi|yagi|spreyi)|el kremi|nemlendirici (krem|losyon|sut|jel)|(yuz|vucut|el|dudak) nemlendirici|pamuk (cubuk|ped)"
                r"|kulak cubugu|tirnak (makasi|torpusu|kesici)|cimbiz|makyaj (fircasi|sungeri)|banyo lifi|\bkese\b|(banyo|dus|hamam) kesesi|dus lifi|\bponza\b"
                r"|yuz maskesi|kisisel bakim seti|tiras (kopugu|jeli|kremi|fircasi)", "", r"battaniye|tam yuz|solunum|gaz maske", "", "other personal care products"),
    ("1329129", r"bebek bezi|hasta bezi|yetiskin bezi", "", "", "", "diapers"),
    ("1329114", r"bebek arabasi|puset|ana kucagi|bebek (oto koltugu|tasima|yuruteci)|portbebe|kanguru|bebek bakim cantasi|oyun parki", "",
                r"supurge|faras", "", "baby articles"),
    (GARDEN_SEATING, r"semsiye", r"bahce|balkon|teras|camping|kamp|plaj|dis mekan", "", "", "garden umbrellas by category"),
    ("1329101", r"valiz|bavul|seyahat (cantasi|seti|organizer|duzenleyici)|seyahat .*yastig|kabin boy|sirt cantasi|\bsemsiye\b|bel cantasi|spor cantasi"
                r"|evrak cantasi|laptop cantasi|kozmetik cantasi|makyaj cantasi", "",
                r"bahce|plaj semsiye|semsiyelik|semsiye (stand|ayagi|tabani|alt)|balkon|teras|capa|alet|takim|parca", "", "travel goods"),
    ("1329104", r"kadin canta|el cantasi|omuz cantasi|plaj cantasi|\bclutch\b|cuzdan|kartlik", "", r"zincir|imperteks|alet|takim", "", "handbags and wallets"),
    ("1329106", r"okul cantasi|anaokulu cantasi", "", "", "", "school bags"),
    ("1329101", r"\bcanta\b|cantasi\b", "", r"aski|organizer|duzenleyici|alet|takim|parca|termal|soguk|buz|imperteks|kemer|profesyonel", "", "other bags"),
    ("1321105", r"kol saati|duvar saati|masa saati|calar saat|alarmli saat|cep saati|dekoratif saat|\bsaat\b", "",
                r"\d+ saat|saat (boyunca|yanma|sure|kadar)|zamanlayici|saatli|priz", "", "watches and clocks"),

    # --- Stationery (09) ----------------------------------------------------
    ("0974001", r"defter|bloknot", "", "", "", "notebooks"),
    ("0974003", r"kursun kalem|tukenmez|boya kalemi|keceli kalem|\bmarker\b|isaret kalemi|fosforlu kalem|dolma kalem|pastel boya|mum boya|\bkalem\b|koli kalemi"
                r"|tahta kalemi|rotus kalemi", "",
                r"kalem pil|kalemlik|(kontrol|test|lehim|tornavida|tutkal|silikon) kalemi|kalem (uc|matkap|keski|tip)|\bpil\b|piller|alkalin|manyetik|miknatis", "", "pens and pencils"),
    ("0974005", r"fotokopi kagidi|a4 kagit|resim kagidi|kraft kagidi|grafik kagidi|fon kartonu|elisi kagidi", "", "", "", "paper"),
    ("0974009", r"kumas makasi|kalemlik|zimba (makinesi|teli)|\batac\b|post it|yapiskanli not|ajanda|\bklasor\b|dosyalik|kartpostal|hediye (paketi|kutusu|cantasi|kesesi|poseti)"
                r"|ambalaj kagidi|kurdele|\bsilgi\b|kalemtras|cetvel|pergel|stick yapistirici|koli bandi|yazi tahtasi|bant dagitici|mantar pano", "",
                r"celik|olcme|delik", "", "other stationery"),

    # --- Clothing and footwear (03) ----------------------------------------
    ("0321102", r"is (botu|cizmesi|ayakkabi)|celik burun|guvenlik (botu|ayakkabisi)|\bcizme\b|\bbot\b", "",
                r"sisme bot|bot (boyasi|bagi|kanca|motoru)", "", "work and rubber boots"),
    ("0321101", r"(guvenlik|erkek) ayakkabi|erkek (terli[kg]|panduf)", "", "", "", "men's shoes"),
    ("0321304", r"cocuk (ev ayakkabisi|ayakkabi)|bebek (patik|ayakkabi)", "", "", "", "children's footwear"),
    ("0321206", r"terli[kg]|panduf|ev botu|ev ayakkabisi|ev patigi|\bpatik\b", "", r"terlik (rafi|dolab|askisi|duzenleyici|standi)|terliklik", "", "slippers"),
    ("0312172", r"erkek cocuk (corap|soket)", "", "", "", "boys' socks"),
    ("0312284", r"kiz cocuk (corap|soket)", "", "", "", "girls' socks"),
    ("0312131", r"erkek (ev )?(corap|soket)", "", "", "", "men's socks"),
    ("0312131", r"corap", r"ayak koruyucu|is guvenli", "", "", "work socks"),
    ("0312243", r"\bcorap|soket corap|kulotlu", "", r"bebek", "", "women's socks"),
    ("0312304", r"\bzibin\b|\bbody\b|bebek (tulum|takim|elbise|body)", "", r"losyon|sut|krem|sprey|mist", "", "baby clothing"),
    ("0312309", r"bebek pijama", "", "", "", "baby pyjamas"),
    ("0312165", r"erkek cocuk pijama", "", "", "", "boys' pyjamas"),
    ("0312276", r"kiz cocuk pijama", "", "", "", "girls' pyjamas"),
    (BATHROBE, r"sabahlik|kimono|\bpanco\b", r"bornoz", "", "", "robes in bathrobe categories"),
    ("0312122", r"erkek (pijama|sabahlik)", "", "", "", "men's pyjamas"),
    ("0312235", r"pijama|gecelik|sabahlik|ev giyim|sort takim", "", "", "", "women's pyjamas"),
    (BATHROBE, r"bornoz|\bpanco\b", "", r"bornozluk|bornoz (askisi|aski)", "", "bathrobe"),
    ("0312116", r"sweatshirt|sweat shirt|\bhoodie\b", "", "", "", "sweatshirts"),
    ("0312105", r"is (montu|mont|ceketi|yelegi|yelek|elbisesi|onlugu)|(reflektorlu|reflektor|ikaz) yelek|\bmont\b|\bmontu\b|softshell|polar (ceket|mont)|\byelek\b"
                r"|yagmurluk", "", r"can yelegi|kopek|kedi", "", "work jackets, vests and rainwear"),
    ("0312110", r"is (pantolonu|pantolon|tulumu|tulum)|salopet|\bpantolon\b|\btulum\b", "", r"bebek|cocuk|kadin|aski", "", "work trousers"),
    ("0312115", r"is gomlegi|erkek gomle[kg]", "", r"gomlek aski", "", "men's shirts"),
    ("0312222", r"\bgomlek\b", "", r"gomlek aski|duzenleyici", "", "shirts"),
    ("0312117", r"(erkek|is) (tisort|t shirt|tshirt)", "", "", "", "men's t-shirts"),
    ("0312270", r"(kiz )?cocuk (tisort|t shirt|tshirt)", "", "", "", "children's t-shirts"),
    ("0312224", r"tisort|t shirt|\btshirt\b", "", r"duzenleyici|organizer", "", "t-shirts"),
    ("0312104", r"pardesu|\bpalto\b", "", "", "", "overcoats"),
    ("0313110", r"esarp|fular|bandana|\batki\b|boyun (atkisi|isiticisi|bandi)|\bbere\b|sapka|\bkep\b", "",
                r"lamba|lambader|abajur|sarkit|avize|aplik|aydinlatma|baret|kask", "", "scarves and hats"),
    ("0313108", r"\bkemer\b|kemeri\b", "", r"emniyet|guvenlik|parasut|bel (destek|korse)|kemerlik|kemerli|iskele|oto|kemer (askisi|aski)"
                r"|\baku\b|saksi|bahce|\bgul\b|delme|canta|istor|aski|perde|tente|raf", "", "belts"),

    # --- Food and beverages (01) -------------------------------------------
    ("0561915", r"(filtre )?kahve (makinesi )?(kagidi|filtresi)|filtre kagidi", "", "", "", "coffee filter paper"),
    ("0122012", r"hazir kahve|granul kahve|nescafe", "", r"makine|fincan|kupa|bardak|kasigi|kavanoz|kutusu|takimi|seti", "", "instant coffee"),
    ("0122011", r"turk kahvesi|filtre kahve|cekirdek kahve|kahve cekirdegi|ogutulmus kahve|espresso kapsul|kapsul kahve", "",
                r"makine|\bmak\b|fincan|kupa|bardak|degirmen|ogutucu|kasigi|kavanoz|kutusu|takimi|seti|sunumluk|tepsisi|cezve|presi|demlik|dripper|\bv60\b|demleme", "", "coffee"),
    ("0123021", r"\bcay\b.*\b(gr|g|kg|poset|demlik poset|bardak poset)\b|siyah cay|yesil cay|bitki cayi|dokme cay", "",
                r"makine|bardak|fincan|kasigi|demlik(?! poset)|caydanlik|tabagi|tepsi|ocak|semaver|suzgec|kutusu|seti|takimi", "", "tea"),

    # --- Tiles named by size (04), before tableware --------------------------
    ("0431102", r"^(?=.*\b\d{1,3}x\d{2,3}\b)(?=.*\b(mat|matt|parlak|rektifiye|rek|lappato|lapp|sugar|r10|r11|1 kalite|porc|porselen)\b)",
                "", r"hali|paspas|kilim|branda|naylon|ortu|sulama|kabin|\bmala\b|malasi", CONSTRUCTION, "tiles named by size and finish"),
    ("0431102", r"^(?=.*\b\d+ ?m2\b)(?=.*\b(\d{2,3}x\d{2,3}|seramik|porselen|parke|laminat|karo|fayans|mat|parlak|rek|k8|1k|2k)\b)",
                "", r"hali|paspas|kilim|branda|naylon|ortu|sulama", CONSTRUCTION, "tiles sold by the square metre"),
    ("0431102", r"porcelen|seranit|granit seramik|seramig|karopan|asma tavan|kartonpiyer|hexagon|antislip|rektifiye",
                "", r"hali|paspas|kilim|branda|naylon|ortu|\bmala\b|malasi", CONSTRUCTION, "tiles named by type"),
    (DECOR, "", r"\btablo|poster|kanvas|biblo|dekoratif (obje|aksesuar)|\baynalar?\b|\bvazo|duvar dekor", "", "", "decor categories"),

    # --- Textiles (052) and carpets (051) ----------------------------------
    ("0431101", r"(naylon|koruma|boya|zemin) .*ortu|koruma ortusu|naylon ortu", "", r"masa|yatak|koltuk|kanepe|sandalye|bahce|mobilya kilif", "", "protective sheets for painting"),
    ("0531401", r"robot supurge|supurge .*(paspas|pedi|yedek|aksesuar|aparat|basligi)", "", "", "", "vacuum cleaner parts"),
    ("0431102", r"duvardan duvara", "", "", "", "fitted carpet"),
    ("0521904", r"pelus banyo|banyo (paspasi|halisi|paspas|kilimi)|klozet (takimi|paspasi|kapak ortusu)|dus paspasi|bambu paspas|paspas takimi", "",
                r"\bkapi\b|oto|arac", "", "bath mats"),
    ("0561106", r"paspas (kova|seti|sapi|bas|aparat|yedegi|sistemi|mop)|\bmop\b|mikrofiber paspas|yer bezi|cekpas|yersil|vileda .*\bsap\b|sapli silece", "", "", "", "mops"),
    ("0511401", r"kapi (onu )?paspas|kapi onu|karsilama paspas|giris paspas|\bpaspas\b|paspasi\b|zemin koruyucu", "", r"\boto\b|arac|araba", "", "door mats"),
    ("0521905", r"masa (ortusu|ortu|yollugu|bezi)|\brunner\b|amerikan servis|\bsupla\b|servis altligi|bardak altligi", "", "", "", "table linen"),
    ("0511401", r"\bhali\b|halisi|halilar|\bkilim|yolluk|\bpost\b|postu\b|shaggy", "",
                r"hali (yikama|sampuan|temizleyici|firca|makinesi|supurge)|suni cim|cim hali|hali (kesme|bicagi)", "", "carpets and rugs"),
    (LIGHTING, r"perde isik|isik perde|led perde|peri isik|yilbasi isik|isik zinciri|aydinlatma zinciri", "", "", "", "lighting: string lights"),
    ("0521102", r"\bstor\b|zebra|jaluzi|plise|dikey perde|bambu perde|rulo perde", "", r"oto|arac|araba|eldiven", "", "roller blinds"),
    ("0521103", r"\btul\b|tul perde|\btulu\b|tuller", "", "", "", "sheer curtains"),
    ("0521101", r"perde|kornis|rustik (cubuk|takim|seti|perde)|cibinlik", "", r"oto|arac|araba|gunes perdesi|yapistirici|ayna", "", "curtains and rails"),
    ("0521201", r"yatak ortusu|yatak ortu|ortu (seti|takimi)|kapitone|lohusa seti|cocuk ortusu|bebek ortusu", "", r"battaniye|yastik", "", "bedspreads"),
    ("0521207", r"\bpike\b|pikesi|muslin|musluin", "", "", "", "pique"),
    ("0521204", r"yorgan", "", r"yorgan (kilif|yuzu)|nevresim", "", "duvets"),
    ("0521208", r"nevresim|carsaf|yastik kilif|kilif seti|ceyiz seti|uyku seti|\balez|yatak (koruyucu|pedi)|lastikli carsaf", "",
                r"kirlent|minder|koltuk|sandalye|\butu\b|utu masa", "", "bed linen"),
    ("0521206", r"battaniye|polar ortu|wellsoft|\bthrow\b|tv ortusu|\bortu\b", "",
                r"kirlent|sisme|kamp|piknik|yangin|masa|koltuk|kanepe|sandalye|klozet|mobilya|bahce|dis mekan|araba|\boto\b|naylon|zemin|boya", "", "blankets and throws"),
    ("0521307", r"havlu\b|havlusu|havlular|pestemal|pestamal|kundak|kurulama bezi|bornoz seti", "",
                r"kagit|havluluk|havlu (aski|tutucu|cubugu|halkasi|rafi|standi|aparati)|islak|temizlik|mikrofiber|dispenser|z kat|yaprak|\brulo\b", "", "towels"),
    ("0819201", r"(telefon|tablet|laptop|macbook|airpods|kulaklik|kamera|ipad|samsung|galaxy|iphone) .*kilif|kilif.* (telefon|tablet|laptop|macbook|airpods|ipad)", "", "", "", "device cases"),
    ("0521905", r"kirlent|minder|dekoratif yastik|alt (degistirme|acma) (pedi|minderi|ortusu)|raf ortusu"
                r"|(koltu[kg]|kanepe|berjer|sandalye|puf|mobilya|uzanma koltugu|tabure) .*(sali|ortusu|kilif)|kanepe (sali|ortusu)|\bsal\b"
                r"|\bkilifi\b|\bkilif\b|kumas pecete|keten pecete|nakisli pecete|\bpecete\b|onlu[kg]|firin eldiveni|tutacak|mangal eldiveni|uyku maskesi"
                r"|kesilmis kumas|perdelik kumas|dosemelik kumas|metre kumas", "",
                r"kagit|tek kullanimlik|yaprak|katli|\b\d\d+ (li|lu)\b|pecetelik|pecete (halkasi|tutucu|kutusu)|utu masa|valiz|bavul|minderli|kilifli", "", "other home textiles"),
    ("0521209", r"yastik|yastigi|yastiklar", "", r"kilif|kirlent|minder|koltuk|dekoratif|seyahat|masaj|oto|arac|kedi|kopek|kamp", "", "pillows"),

    # --- Cleaning and non-durable household goods (056) ---------------------
    ("0561102", r"bulasik (deterjan|sivisi|tableti|kapsul|parlatici|tuzu|jeli|tozu)|bulasik makinesi (deterjan|tablet|kapsul|parlatici|tuzu|temizleyici|kokusu)"
                r"|elde yikama", "", "", "", "dishwashing products"),
    ("0561101", r"camasir (deterjan|yumusatici|tozu|kapsul|tablet|jeli|parfumu|sodasi|kokusu)|sivi deterjan|toz deterjan|\bmatik\b|yumusatici"
                r"|leke (cikarici|sokucu|cikartici)|beyazlatici|renk (koruyucu|tutucu)|perdematik|camasir kurutma (mendili|topu)|kurutma top|deterjan", "",
                r"bulasik|yuzey|banyo|mutfak|\byer\b|\bhali\b|koltuk|\boto\b|arac|\bel\b|deterjanlik|firca|kabi|kab seti|saklama|\bwc\b|klozet|\bcam\b|glass", "", "laundry products"),
    ("0721302", r"temizleyici|koku|sprey|parlatici|cila|sampuan|wax|pasta|bakim", r"\boto\b|otomotiv", "", "", "car care by category"),
    ("0561103", r"yuzey temizle|yer temizle|cok amacli temizle|camasir suyu|cam (temizleyici|temizleme)|banyo temizle|mutfak temizle"
                r"|kirec (sokucu|cozucu|onleyici)|kir sokucu|yag (sokucu|cozucu)|tuvalet temizle|klozet (blok|temizle|jel)|lavabo acici|gider acici"
                r"|ovma (tozu|kremi)|krem temizleyici|arap sabunu|sabun tozu|mobilya (cilasi|parlatici|temizleyici)|(ahsap|parke|deri|inox|celik|firin|ocak) temizleyici"
                r"|wc (temizle|blok|jel|kokusu)"
                r"|(hali|koltuk) (sampuan|temizleyici)|dezenfektan|hijyen (sivisi|spreyi)|amonyak|tuz ruhu|kostik|temizlik (sivisi|spreyi|kopugu|jeli)|temizleyici\b"
                r"|(cam|glass) .*deterjan",
                "", r"\bcilt\b|\byuz\b|\boto\b|arac|lens|gozluk|ekran|klavye|makine|akulu|robot|\d+ ?v\b|spiral|susta|kaynak|hava temizle|kartus|brush|universalbrush", "", "surface cleaning products"),
    ("0561902", r"strec film|\bstrec\b|aluminyum folyo|\bfolyo\b|(buzdolabi|buz dolabi) (poseti|torbasi)|saklama poseti|kilitli poset|zip poset|pisirme (kagidi|torbasi|poseti)"
                r"|firin (kagidi|torbasi|poseti)|yagli kagit|gida poseti|dondurucu poseti", "", r"hurc|yorgan|giysi|kiyafet|bant|yapiskanli|d c fix", "", "storage and preservation materials"),
    ("0561903", r"kagit havlu|havlu kagit|kagit pecete|\bpecete\b|kagit (tabak|bardak|kase)|karton (bardak|tabak)|plastik (tabak|bardak|catal|kasik)"
                r"|tek kullanimlik|rulo havlu|z katlama", "", r"pecete (halkasi|tutucu|kutusu|lik)|pecetelik|nakisli|keten|kumas|dantel|havluluk|aparat|tutucu|standi|dispenser|askisi", "", "paper tableware"),
    ("0721302", r"(oto|arac) fircasi", "", "", "", "car brushes"),
    ("0561106", r"temizlik bezi|mikrofiber|\bbez\b|bezi\b|sunger|celik tel|tel sunger|ovma teli|cam bezi|guderi|mucize bez|toz (bezi|alici|alma)|cam sil|\blif\b|ped lif"
                r"|(banyo|dus|cam|pencere) silece",
                "", r"bebek|canta|torba|makyaj sungeri|zimpara|boya|sapan|halat|klozet|sungerli|rulo|dolap|ayakkabilik|gardirop|polisaj|boru|bant|cirpici", "", "cleaning cloths and sponges"),
    ("0561915", r"dikis (ipligi|seti)|kumas tebesiri|takoz firca|kesilmez eldiven|muayene eldiven|eldiven nitril|gider fircasi|nem alici (tablet|yedek)"
                r"|bahce supurgesi|koltuk yikama fircasi|farasli supurge|samdan mum\b", "", "", "", "household sundries named plainly"),
    ("0561915", r"cop (poseti|torbasi|torba)|naftalin|sinek (kovucu|ilaci|spreyi|kapani|raketi)|bocek (ilaci|spreyi|kapani)|hamam bocegi|karinca"
                r"|fare (zehiri|kapani|yapiskani)|haserat|kovucu|sivrisinek|\bmum\b|mumu\b|mumlar|tealight|tea light|kibrit|\bcakmak\b|tutusturucu"
                r"|oda (kokusu|parfumu|spreyi)|ortam (kokusu|spreyi)|dolap kokusu|cubuklu|difuzor|koku (tasi|cubugu|seti|bari|kesesi)|esans|buhurdanlik|tutsu|girgir"
                r"|(hali|koltuk|yer|tuvalet|klozet|bulasik|sise|elbise|ayakkabi|copcu|supurge) fircasi"
                r"|ayakkabi (boyasi|cilasi|spreyi|kremi|sungeri)|tabanlik|supurge (torbasi|filtresi)|toz torbasi|mandal|faras|cali supurge|sapli supurge"
                r"|plastik supurge|kil supurge|yer fircasi|tuvalet fircasi|klozet fircasi|bulasik fircasi|sise fircasi|(bulasik|temizlik|lateks|nitril|vinil) eldiven",
                "", r"samdan|mumluk|mum tabag|\bfener\b|cakmak (sarj|tasi)|fircaligi|fircalik|kilit|barel|kiskac|isken|torch|purmuz", "", "other non-durable household goods"),

    # --- Major and small appliances (053) -----------------------------------
    ("0531101", r"buzdolabi|buz dolabi|\bmini ?bar\b|sarap sogutucu|icecek sogutucu", "",
                r"buzdolabi (poseti|torbasi|posteri|magnet|susu|organizer|duzenleyici|kabi|saklama|kokusu|temizleyici|filtresi|rafi|kolu)|kamp|modul"
                r"|organizer|saklama|\bkap\b|kabi|poset|torba", "", "refrigerators"),
    ("0531103", r"derin dondurucu|\bdondurucu\b|sandik tipi", "", r"donduruculu|saklama|kabi|\bkap\b|organizer|poset", "", "deep freezers"),
    ("0531106", r"bulasik makinesi|bulasik makinasi", "", r"tamir|kurutmalik|altligi|ayak|sepeti|hortum|filtre", "", "dishwashers"),
    ("0531201", r"camasir makinesi|camasir makinasi|kurutmali camasir", "",
                r"dola[pb]|ustu|rafi|kilifi|ortusu|altligi|ayagi|tamir|hortum|filtre|sepeti|torba|temizleyici|musluk|muslugu|vana", "", "washing machines"),
    ("0531202", r"kurutma makinesi|camasir kurutucu", "", r"\bsac\b|\bel kurutma|kurutmalik", "", "dryers"),
    ("0531303", r"\bsoba\b|sobasi|isitici|isiticisi|yagli radyator|konvektor|infrared|quartz (isitici|soba|infrared)|halojen isitici|somine|kat kalorifer sobasi|kuzine|ates cukuru"
                r"|mantar isitici|termo ?ventilator", "",
                r"\bsu isitici|kettle|isitici (pad|ped|yastik|minder|bant|kablo)|biberon|\bsut isitici|mum isitici|wax|\bsac\b|ayak isitici|akvaryum"
                r"|isiticili (koltuk|yatak)|isitma (kablo|bant)|sise isitici|termometre|olcum", "", "heaters and stoves"),
    ("0531306", r"\bkombi\b|kombisi|yogusmali|termosifon|sofben|anlik su isitici|boyler|kat kaloriferi|kalorifer kazani|panel radyator|\bpetek\b"
                r"|isi pompasi|gunes enerjili|odun kazani", "", r"kombi (dolabi|bacasi)|petek (temizleyici|fircasi)|bolmeli|organizer|duzenleyici|cekmece|lamba|aydinlatma|isik|\bled\b", "", "combi boilers and water heaters"),
    ("0531301", r"klima|\bsplit\b|vantilator|\bfan\b|hava sogutucu|evaporatif|nem (alma|alici)|hava nemlendirici|ultrasonik nemlendirici|hava temizle|iyonizer"
                r"|aspirator fan|banyo aspirator|havalandirma", "",
                r"klima (temizleyici|sprey|kumanda|aparat|aski|braket|montaj)|fanli isitici|bilgisayar fani|isitici|fan (kayis|motoru|pervane)|toprak|\bcim\b", "", "air conditioning and fans"),
    ("0531108", r"tutusturma bacasi|komur (ayirma|tirmigi|sepeti)|baca takimi|\bweber\b", "", r"briket|\d+ ?kg\b", "", "barbecue accessories"),
    ("0531108", r"\bfirin\b|firini\b|ankastre (firin|ocak|set|davlumbaz|aspirator|mikrodalga)|\bocak\b|set ustu|cam ocak|induksiyon|elektrikli ocak|gazli ocak"
                r"|gozu gazli|\d+ gozlu (ocak|gazli|cam|ankastre|set)|mikrodalga|davlumbaz|aspirator|kuzine|mangal|barbeku|barbekue|\bgrill\b", "",
                r"firin (eldiveni|kabi|kalibi|tepsisi|torbasi|poseti|kagidi|temizleyici|termometre|fircasi|onlugu|teli|lambasi|rafi|tutacak)"
                r"|ocak (alti|ustu|temizleyici|koruyucu|kapagi|tupu)|mangal (sis|izgara|eldiven|komur|firca|kibrit|tutusturucu|masa)|kamp ocag|piknik ocag"
                r"|uygun|saklama|kabi|tava|tencere|tabanli|borusu",
                "", "ovens, cookers, barbecues"),
    ("0531401", r"akulu cam temizle|cam vakum|supurge|buharli temizle|buharli temizlik|buhar (temizleyici|makinesi)|hali yikama makinesi|koltuk yikama makinesi|islak kuru|vakum (makinesi|temizleyici)"
                r"|cam (temizleme|silme) (makinesi|robotu)|basincli yikama|yuksek basincli|yer silme robotu|karcher", "",
                r"supurge (torbasi|filtresi|hortumu|aparati|fircasi|basligi|yedek|aksesuar|ucu|sapi)|cali|sapli|plastik supurge|faras|supurgelik|oto supurge|yaprak supurge"
                r"|kil supurge", "", "vacuum and cleaning machines"),
    ("0532101", r"dilimleme aparat|blender|dograyici|\brondo\b|mutfak robotu|mutfak sefi|mikser|cirpici|smoothie|meyve sikacagi|elektrikli narenciye|kati meyve|hamur yogurma"
                r"|hamur karistir|stand mikser|kitchenaid|thermomix|kiyma makinesi|elektrikli rende", "", r"manuel|mekanik|ipli|eviye|evye|\btel\b", "", "blenders and food processors"),
    ("0532201", r"cay makine|kahve(si)? makine|kahve mak\b|espresso makine|kettle|su isiticisi|su isitici|semaver elektrik|kahve (ogutucu|degirmeni) elektrik|sut kopurtucu|nespresso|dolce gusto",
                "", r"kagidi|kagit|filtresi|kirec|temizleyici|manuel", "", "beverage appliances"),
    ("0532102", r"tost makine|ekmek kizartma|air ?fryer|fritoz|waffle|krep makinesi|gozleme makinesi|pisirici|multi ?cooker|slow cooker|yogurt makinesi|ekmek (yapma|makinesi)"
                r"|pizza makinesi|misir makinesi|cikolata cesmesi|dondurma makinesi|sandvic makinesi|elektrikli (izgara|tencere|wok|tava)|izgara makinesi"
                r"|mutfak tartisi|vakumlama|biberon isitici|yumurta pisirici|meyve kurutma|poset (kapatici|yapistirici)", "", "", "", "small cooking appliances"),
    ("0532901", r"\butu\b|\butusu\b|buharli duzlestirici|dikey buharli|kiyafet buharlayici|utu masa|tuy temizleme", "", r"\bsac\b", "", "irons, ironing boards, garment care"),

    # --- Glassware, tableware and utensils (054) ---------------------------
    ("0540316", r"seyahat bardag|to go|termos|matara|vakumlu (bardak|sise|kupa|mug)|travel mug|su (sisesi|matarasi)|\bsuluk\b|isi yalitimli (bardak|sise|kupa)|termo (bardak|kupa)", "",
                r"termosifon|termostat|termometre|termal canta|termos canta", "", "thermos and bottles"),
    ("0540201", r"\bcatal|kasik\b|kasigi|kasiklar|tatli (catali|kasigi)|bicak (seti|takimi|bloku|blogu|standi)|(mutfak|sef|ekmek|meyve|steak|santoku|pirzola|et|sebze|peynir|domates|soyma|tirtikli|yemek) bica[kg]"
                r"|\d+ ?(li|lu) bicak|bicak \d+ cm|hamur jileti"
                r"|bicak bileyici|bicaklik|cutlery|servis (kasigi|catali)|dograma bica[kg]|buyuk bicak", "",
                r"catal (anahtar|uclu|agiz)|kasik (anahtar|uc|matkap)|kasiklik|modul|olcu|olcek|organizer|duzenleyici|bolme", "", "cutlery and kitchen knives"),
    ("0540104", r"yumurta kadehi|yumurtalik", "", r"\bcam\b|camdan", "", "egg cups"),
    ("0540102", GLASS, "", r"kapak (tutucu|standi)|dekoratif|parfum", "", "glassware by material"),
    ("0540102", r"bardak|bardagi|kadeh|surahi|kavanoz|borcam|pyrex|french press|\bsise\b|sisesi\b|karaf|yaglik|tereyagli[kg]", "",
                r"kagit|plastik|karton|altligi|bardaklik|dis fircasi|porselen|seramik|stoneware|melamin|celik|tek kullanimlik|olcu|sprey|sabunluk|pompa"
                r"|dekoratif|parfum", "", "glassware"),
    ("0540104", r"porselen|seramik (kase|tabak|kupa|fincan|demlik|servis|sunum|tepsi)|stoneware|bone china|\bbone\b|fincan|\bkupa\b|kupasi\b|\bmug\b|tabak|tabagi|tabaklar"
                r"|\bkase\b|kasesi|kaseler|yemek takimi|kahvalti (takimi|seti)|(cay|kahve|espresso) (takimi|seti)|sunumluk|cerezlik|sosluk|sufle|demlik|yemek seti|melamin"
                r"|kek standi|pasta standi|servis (set|seti|tabagi)|oval servis|kurabiyelik|lokumluk|sekerlik|tatlilik", "",
                r"kagit|plastik tabak|tek kullanimlik|karton|kopek|kedi|mama|celik (tabak|kase)|saksi|sabun|kul tablasi|kulluk|tablasi|tabaklik|bardaklik", "", "porcelain and ceramic tableware"),
    ("0540301", r"(celik|paslanmaz|inox|bakir|aluminyum) (tencere|tava|cezve|caydanlik|demlik|kase|sahan|tepsi)|\b3 ?ply\b|tri ?ply", "", "", "", "steel cookware"),
    ("0540314", r"pisirme mati|silikon mat\b|yapismaz|teflon|granit|seramik kaplama|titanyum|non ?stick|dokum|plancha|planca|kek kalibi|muffin|tart kalibi|\bwok\b|krep tavasi|\btava\b|tavasi",
                "", r"eviye|evye|lavabo|tezgah|mermer|seramik (karo|fayans|yer|duvar|levha)|matkap|panc|disk|kesici|beton|dokum (soba|somine|radyator|kapak)|harc|yapistir"
                r"|spatula|sapi|tutacag|kilit|kilidi", "", "non-stick and cast cookware"),
    ("0540301", r"tencere|duduklu|cezve|caydanlik|semaver|sahan|sutluk|guvec|kepce|spatula|kevgir|suzgec|rende|kesme tahtasi|sarimsak (ezici|presi)|soyaca[kg]|soyucu"
                r"|acacak|tirbuson|limon sikacagi|cirpma teli|merdane|oklava|tuzluk|biberlik|baharatlik|baharat (seti|takimi|kavanozu|standi|rafi)|ekmeklik|ekmek (kutusu|sepeti)"
                r"|meyvelik|tepsi|tepsisi|firin (kabi|kalibi|tepsisi)|saklama kab|erzak|sefer tasi|sos kabi|buz kalibi|izgara|\bsis\b|olcu (kasigi|kabi)"
                r"|mutfak (makasi|seti|gereci|aleti|rafi|duzenleyici|organizer)|kasiklik|bulasik (sepeti|rafi|kurutmalik)|bulasiklik|damlalik|cay suzgeci|moka pot"
                r"|pizza (kesici|tasi)|ogutucu|ayiklayici|bakrac|\bkabi\b|kaplari|pecetelik|servis arabasi|sisel[ii]k|degirmen|ezici|elegi|\belek\b"
                r"|kurabiye kalib|plastik kap\b|kap seti|duzenleyici", "",
                r"izgara (gider|kapak|menfez)|\bfan\b|havalandirma|sabun|dis firca|banyo|kalem|\bcop\b|kedi|kopek|mama kab|dekoratif", "", "kitchen utensils and articles"),

    # --- Furniture (051) -----------------------------------------------------
    # Lamp listings often name the rooms they suit ("Yatak Odası Salon Avize").
    (LIGHTING, r"avize|\baplik\b|aplik (lamba|aydinlatma)|lambader|abajur|plafonyer|sarkit", "", "", "", "lighting named before furniture"),
    (GARDEN_CHAIR, r"bahce (sandalye|koltu[kg]|tabure)|balkon sandalye|plastik sandalye|katlanir sandalye|markiz sandalye|sezlong|\bplaj sandalye", "", r"sallanan", "", "garden chairs and loungers"),
    (GARDEN_TABLE, r"bahce (masa|masasi|masa takimi|orta sehpa|yan sehpa|sehpa)|balkon masa|piknik masasi|mutfak adasi", "", "", "", "garden tables"),
    (GARDEN_SEATING, r"bahce (takimi|oturma|kose|salincak|mobilya|kanepe)|balkon (takimi|oturma|kose)|rattan|\bsalincak\b|hamak|\bcardak\b|pergola"
                     r"|bahce semsiye|balkon semsiye|dis mekan (koltu|kanepe|oturma|sehpa)|mini takim", "", "", "", "garden seating and shade"),
    ("0511115", r"genc odasi|cocuk odasi|bebek odasi|\branza\b|\bbesik\b|cocuk (karyola|yata[kg]|gardiro[pb]|dola[pb]|masa|sandalye|koltu[kg]|kitapli[kg]|komodin)"
                r"|bebek (karyola|yata[kg]|dola[pb]|komodin)|calisma (masasi|koltu[kg]|sandalyesi|odasi)|ders calisma|ogrenci masasi|bilgisayar masasi|oyuncu (masasi|koltu[kg])"
                r"|ofis (koltu|sandalye|masa|calisma)|ofis .*(sandalye|koltu[kg])|buro (sandalye|koltu)|yonetici (koltu|masa)|\bkeson\b|toplanti masa|montessori|playstation .*koltu[kg]|gaming (koltu|chair)"
                r"|mama sandalye|alt degistirme (masasi|unitesi)|bebek bakim (masasi|unitesi)", "",
                r"avize|aplik|lamba|aydinlatma|sarkit|plafonyer", "", "youth, children's, study and office furniture"),
    (KITCHEN_CABINETS, r"mutfak .*dola[pb]|mutfak (modul|unite)|hazir mutfak|ankastre mutfak|kiler dola[pb]|tezgah ustu dolap|ust dolap|alt dolap", "", "", "", "kitchen cabinets"),
    ("0431108", r"banyo .*dola[pb]|lavabo dola[pb]|banyo mobilya", "", "", "", "bathroom cabinets"),
    ("0511108", r"yatak odasi|gardiro[pb]|elbise dola[pb]|sifonyer|komodin|makyaj masasi|tuvalet masasi|ceyiz sandig|giysi dola[pb]|dugun paketi|manikur (pedikur )?masasi"
                r"|\d+ (\w+ )?kapakli.*dola[pb]|dolap ve yukluk|yukluk", "", r"avize|aplik|lamba|aydinlatma|sarkit|plafonyer", "", "bedroom furniture"),
    ("0511111", r"\byatak\b|yatagi\b|yataklar|karyola|somya|misafir yatagi|ortopedik yatak|visco yatak|yayli yatak|pocket|sunger yatak|katlanir yatak|\bdivan\b", "",
                r"yatak (odasi|basligi)|\bbaza\b|sisme", "", "beds and mattresses"),
    ("0511114", r"\bbaza\b|bazasi\b|yatak basligi|karyola basligi|\bbaslik\b|lata|cita tabani", "", r"pabuc|pimi", "", "bed bases and headboards"),
    ("0511102", r"mutfak masa", "", "", "", "kitchen tables"),
    ("0511116", r"metal raf|celik raf|depo raf|raf seti|\braf\b \d+ basamak|etajer", "", "", "", "shelving units"),
    ("0511116", "", r"raflar ve dolaplar", "", "LoyaMakina", "Loya shelving category"),
    ("0511117", r"yemek odasi|masa sandalye takimi|masa takimi|\bkonsol\b|konsolu|\bbufe\b|vitrin|camli dola[pb]|dresuar|kahve kosesi", "",
                r"\braf\b|ferforje|braket|\btv\b|sehpa|aynasi\b", "", "dining room furniture"),
    ("0511116", r"oturma takimi|koltuk takimi|kose takimi|kose koltu[kg]|(sol|sag|l|u) kose|kose (kanepe|oturma|parcasi)|\bkose $|kanepe|cekyat|berjer|tekli koltu[kg]|ikili koltu[kg]|uclu koltu[kg]|\bkoltu[kg]|chester|sallanan sandalye"
                r"|markiz|cerceve rafi|sallanan sezlong"
                r"|dinlenme koltu[kg]|\bpuf\b|\bbench\b|tv unite|televizyon unite|tv sehpa|tv dola[pb]|medya unite|sehpa|zigon|kitapli[kg]|duvar rafi"
                r"|duvar unitesi|raf unitesi|dekoratif raf|ayakkabilik|portmanto|vestiyer|hol dolabi|cok amacli dola[pb]|kombinasyon|oturma grubu|oturma odasi"
                r"|salon takimi|moduler (kanepe|koltu[kg]|unite)|\bunite\b|unitesi|paravan|dola[pb]", "",
                r"koltuk (ortusu|sali|kilifi|minderi|yikama|yastigi|alti|ayagi|temizle)|\boto\b|arac|araba|matkap|testere|tezgah|kaynak|duzenleyici|organizer"
                r"|kilidi|kilit\b|mentese|kulpu|\bray\b", "", "living room and other cabinets"),
    ("0511102", r"yemek masa|\bmasa\b|masasi\b|bistro|bar masasi|katlanir masa|acilir masa|masa ayagi|masa tablasi", "",
                r"masa (lambasi|saati|ustu|tenisi|alti|takvimi|tipi|vantilator|fani)|\bis masasi|tezgah|ameliyat", "", "tables"),
    ("0511105", r"sandalye|tabure|bar taburesi|\bbank\b", "", r"sandalye (ayagi|tekerlegi|kecesi|altligi)|kamp|plaj", "", "chairs and stools"),

    # --- Dwelling maintenance materials (04) --------------------------------
    ("0454101", r"mangal komuru|\bkomur\b|komuru\b|briket komur", "", r"komur (kovasi|masasi|kuregi)|kalem", "", "coal and charcoal"),
    ("0454201", r"\bodun\b|\bpelet\b|tutusturma odunu|\bcira\b", "", r"odun sobasi|pelet soba|kanca|kancasi|kazan|kirici|balta", "", "firewood"),
    ("0431101", r"(boya|yagli boya|robot|kestirme|yassi|radyator|badana|vernik|duvar|tavan) fircasi|firca no|boya (firca|rulo|tekne|kab|bandi)"
                r"|\brulo\b|rulosu|maskeleme bandi|\bsirik\b|raspa|raspasi|ispatula|(duvar|boya|macun) spatula", "", r"rulo (havlu|kagit|poset)", "", "painting tools"),
    ("0431101", r"\bboya\b|boyasi|boyalar|astar|verni[kg]|\bcila\b|cilasi|\blake\b|emaye|epoksi|ahsap koruyucu|emprenye|selulozik|tiner|sprey boya|antipas|pas (sokucu|onleyici)"
                r"|ic cephe|dis cephe|\bdyo\b|polisan|marshall|filli boya|jotun|permolit|metalik (gumus|altin|bakir)", "",
                r"ayakkabi|\bsac\b|hobi|resim|kumas|\bcam boya|seramik boya|kalem|\boto\b|arac|rotus|boyama|tablo|kanvas|macun|akulu|sistemi"
                r"|tepsi|tabak|kase|tencere|dekoratif|polisaj|sungeri|motor", "", "paints and coatings"),
    ("0431102", r"seramik\b|seramig|fayans|\bkaro\b|\bparke\b|laminat|vinil (parke|zemin|kaplama)|\bspc\b|\blvt\b|duvar kagidi|duvar paneli|duvar kaplama|lambiri|supurgelik"
                r"|mozaik|mermer (karo|plaka)|traverten|tas kaplama|zemin kaplama|pvc kaplama|esik profili|doseme|tezgah arkalik|kartonpiyer|asma tavan", "",
                r"seramik (kesici|kesme|matkap|uc|delici|yapistirici|derz|tava|tencere|kase|tabak|kupa|fincan|vazo|saksi|isitici|bicak|barbeku|demlik)"
                r"|fayans (kesici|kesme|matkap|uc|yapistirici|derz)|duvar kagidi (sokucu|tutkali|yapistiricisi)|doseme (cakma|teli|zimba)|bust|tablo|cerceve|biblo|obje|vazo|tepsi|sehpa|masa|aksesuar"
                r"|yapistiricisi|kadehi|yumurta", "", "floor and wall coverings"),
    ("0431106", r"pvc (kapi|pencere|dograma)|ic kapi|celik kapi|amerikan kapi|\bkapi\b|\bpencere\b|sineklik|panjur|kepenk|cam balkon", "",
                r"kapi (kolu|kilidi|zili|stoperi|tamponu|mentes|aski|arkasi|kancasi|durbunu|gozu|zinciri|yayi|fitili|kulpu|kapatici|sensor|numara)|kapak|rozet|hidrolik|makara|fitil|aparat|\bray\b|\byay\b"
                r"|pencere (sensor|alarm|kilidi|kolu|temizleme|robotu|fitili|filmi)|dolap kapi"
                r"|yayi|reze\b|rezesi|stobu|\bstop\b|otomatig|fircasi|mastik|kilit\b|kilidi|barel|bandi", "", "doors and windows"),
    ("0431108", r"batarya|musluk|(banyo|lavabo|evye|eviye|dus|mutfak|ankastre) armatur|\bvana\b|vanasi|\bvalf\b|valfi|rakor|nipel|\bdirsek\b|manson|pprc|\bppr\b|\bboru\b|borusu|fitting|sifon|\bgider\b"
                r"|dus (seti|basligi|takimi|sistemi|teknesi|kabin|hortumu|spirali)|dusakabin|\bkabin\b|spiral takimi|klozet|rezervuar|lavabo|evye|eviye|kuvet|pisuvar"
                r"|taharet|\bbide\b|flex hortum|spiral hortum|su (filtresi|aritma|sayaci)|hidrofor|teflon bant|sizdirmazlik bandi|\bconta\b|kollektor"
                r"|radyator (vanasi|tapasi)", "",
                r"klozet (fircasi|takimi|paspasi|kapak ortusu|blok|temizle|jel)|aydinlatma|led armatur|etanj|floresan armatur|solenoid|kabin boy|kilit|kilidi"
                r"|krose|kelepce|klips|hortum (baglanti|adaptor|konnektor|tabancasi)|bahce", "", "plumbing and sanitary"),
    ("0431109", r"yangin (tupu|sondurucu|battaniyesi)|sondurucu|duman dedektor|gaz dedektor|guvenlik kamera|alarm (seti|sistemi|paneli)|kapi telefonu|diafon|interkom"
                r"|goruntulu (diafon|kapi)", "", "", "", "home security equipment"),
    ("0431109", r"cimento|\balci\b|alcipan|\bsiva\b|\bharc\b|harci\b|\bbeton\b|tugla|briket|gazbeton|ytong|\bkum\b|cakil|kirec|derz|yapistirici|silikon|mastik"
                r"|poliuretan|pu kopuk|montaj kopugu|izolasyon|yalitim|membran|bitum|mantolama|tasyunu|camyunu|\bxps\b|\beps\b|strafor|kontrplak|\bosb\b|\bmdf\b"
                r"|\bsunta\b|kereste|\bcita\b|kalas|macun|kiremit|onduline|trapez|mahya|\boluk\b|cati (kaplama|membran)|pencere cami|cam levha|temperli cam"
                r"|sac levha|demir (profil|lama|kosebent)|insaat demiri|celik hasir|\bprofil\b|tutkal|polikarbon|akustik|mudahale kapag|\bkopuk\b|kopugu"
                r"|cift tarafli bant|izole bant|tamir bandi|yapiskanli bant|aluminyum bant|montaj bandi", "",
                r"silikon (kalip|spatula|kase|kapak|mat|ped|firca|kulp|baharat|eldiven|tava|tencere|kek|muffin|saklama)|dis macunu|beton (matkap|ucu|delici|civi|vidasi|dubel|kesme)"
                r"|tabanca|testere|bica[kg]|matkap|\buc\b|ucu\b|kesici|disk|zimpara|kesme|delici|freze|tiras|dus kopugu|siva (alti|ustu)|\bspot\b|\bled\b|armatur|saksi",
                "", "other maintenance materials"),

    # --- Lighting, batteries, decor, storage, bath accessories ---------------
    ("0552201", r"\bpil\b|piller\b|pili\b|kalem pil|ince pil|dugme pil|alkalin|sarj edilebilir pil|pil sarj|\b(aa|aaa|9v|cr2032|lr44|lr03|lr6|23a|27a)\b", "",
                r"\baku\b|akulu|pil (yuvasi|kutusu|kapagi|dahil)|gunes|solar|lamba|lambasi|fener|feneri|\bisik", "", "batteries"),
    ("0552203", r"ampul|\bfloresan\b|halojen|\b(e27|e14|gu10|mr16)\b|tasarruflu lamba|led lamba", "", r"\bduy\b|duylu|\boto\b|\bfar\b", "", "light bulbs"),
    (LIGHTING, r"glob cami|avize|lambader|abajur|aplik|sarkit|\bspot\b|plafonyer|led panel|projektor|lamba|lambasi|el feneri|kafa feneri|\bfener\b|aydinlatma|armatur"
               r"|led (serit|isik)|serit led|solar (lamba|aydinlatma)|\blm\b|\bled\b", "",
               r"mumluk|tealight|kamp", "", "lighting fixtures"),
    (DECOR, r"ayna|aynasi", "", r"\boto\b|arac|dikiz", "", "mirrors"),
    (BATH_ACCESSORIES, r"askilik|\baski\b|askisi|\braf\b|rafi\b|sepet|kanca|tutucu|organizer|duzenleyici|stand|verici|dispans|dispens|sampuanlik", r"banyo", r"camasir", "", "bath accessories by category"),
    (STORAGE, r"saklama (kutusu|torbasi)|camasir (sepeti|torbasi|kurutmalik|kurutma askisi)|kurutmalik|hurc|duzenleyici|organizer|\baski\b|askisi|askilik"
              r"|\bsepet\b|sepeti|cop kovasi|cop kutusu|\bkutu\b|kutusu|\bsandik\b|\bpano\b|panosu|anahtarlik|kapakli kutu|tel sepet|cekmece", "",
              r"oyuncak|yilbasi|hortum", "", "storage and organisers"),
    (DECOR, r"vazo|cerceve|\btablo\b|kanvas|biblo|\bobje\b|heykel|\bbust\b|yapay|dekoratif|samdan|mumluk|duvar susu|sticker|poster|\bresim\b|\bfigur|kul tablasi|kulluk"
            r"|kum saati|cicek (sepeti|aranjman)|teraryum|harfler|cicekli?k", "", "", "", "decor"),
    (BATH_ACCESSORIES, r"sabunluk|sabunlugu|dis fircalik|dis fircaligi|havluluk|havlu (askisi|cubugu|halkasi|rafi)|tuvalet kagitlik|tuvalet kagidi (tutucu|aparati|standi)"
                       r"|kagitlik|banyo (seti|rafi|aksesuar)|dus (rafi|oturagi)|kose rafi|bornozluk|dispenser|fircalik|fircaligi|tuvalet fircasi", "", "", "", "bath accessories"),

    ("0532101", r"\w", r"kucuk ev aletleri", "", "EnglishHome", "EnglishHome small appliance parts"),

    # --- Garden, tools, fittings, work safety --------------------------------
    (GARDEN, r"saksi|toprak|gubre|tohum|\bfide\b|\bbitki\b|\bcicek\b|\bcim\b|suni cim|hortum|sulama|fiskiye|budama|tirpan|\bcapa\b|tirmik|el arabasi|golgelik|bahce"
             r"|cim bicme|cit (teli|kesme)|\bsera\b|ilac pompasi|pulverizator|\bkurek\b|\borak\b|dirgen|yaba\b|meyve toplayici|sumbul|lale sogan|misina", "",
             r"\bfis\b|fisi\b|priz|toprakli", "", "garden"),
    (WORK_SAFETY, r"eldiven|baret|\bkask\b|koruyucu gozluk|guvenlik gozlug|is gozlugu|usta gozlugu|\bmaske\b|maskesi|kulak (koruyucu|tikaci)|antifon|emniyet kemeri"
                  r"|parasut tipi|yuz siperi|dizlik|is guvenlik|reflektif", "", "", "", "work safety"),
    (FITTINGS, r"matkap uclu vida|(tekli|ciftli|vavien|komutator|light|sıva alti|siva alti|siva ustu|grup) anahtar|anahtar (priz|kapak|cerceve|modul)|vavien|komutator"
               r"|\bpriz\b|prizi|grup priz|uzatma kablosu|sigorta|kacak akim|\brole\b|rolesi|klemens|\bbuat\b|kablo kanali|elektrik panosu|\bzil\b|zili|dimmer"
               r"|termostat|\bfis\b|\bduy\b|duylu|kablo (bagi|papucu)|makaron|\bcat ?[56]\b|rj45|\bplug\b|(izole|kaucuk|eriyen|elektrik|pvc) bant|karabina", "",
               r"matkap(?! uclu vida)|taslama|testere|vidalama|zimpara|kirici|delici|planya|freze|dekupaj|kaynak|havya|polisaj|tabanca", "", "electrical fittings"),
    (TOOLS, r"matkap|vidalama|tornavida|pense|pensi|kargaburun|keski|cekic|testere|taslama|zimpara|\bege\b|egesi|torpu|iskarpela|\bmala\b|malasi|spatula|serit metre|su terazisi"
            r"|lazer|gonye|iskence|mengene|kompresor|kaynak|havya|lehim|freze|planya|dekupaj|kirici|delici|kriko|merdiven|takim (cantasi|arabasi)|alet cantasi|\buc\b|uclari"
            r"|ucu\b|\bbits\b|lokma|anahtar|circir|panc|kesici|disk\b|diski|karot|olcum|olcer|multimetre|tabanca|havali|pnomatik|akulu|\baku\b|polisaj|motor\b|pompa"
            r"|tel firca|kesme|delme|sokme|soku|cektirme|alet|makas|bicak|bicagi|pistole|perforator|kumpas|kurt agzi|tokmak|bileme|engraver|raspa|kaziyici|manivela"
            r"|tasima arabasi|elmasli|v kayis|kayis\b|\bdremel|hilti|bosch|makita|dewalt|einhell|metabo|ryobi|stanley|izeltas|ceta form|knipex|proxxon|kirschen", "",
            "", "", "tools"),
    (FITTINGS, r"\bvida\b|vidasi|vidalar|civata|somun|\bpul\b|pulu\b|rondela|dubel|percin|\bcivi\b|civisi|kanca|mentese|kulp\b|kulpu|kapi kolu|kilit|kilidi|barel"
               r"|stoper|\bstop\b|zincir|halat|sapan|kelepce|kosebent|baglanti|\bray\b|rayi|amortisor|\bayak\b|ayagi|tekerlek|teker\b|makara|\byay\b|yayi\b|\btel\b|teli\b"
               r"|tel orgu|\bip\b|urgan|mapa|braket|raf (destegi|tasiyici|alti|tutucu)|miknatis|magnet|yuksuk|\btapa\b|tapasi|krose|topuz|\bkablo\b|kablosu|elektrik", "",
               "", "", "fittings and hardware"),

    # --- Category fallbacks --------------------------------------------------
    (FITTINGS, "", r"mobilya", "", "AfeksYapiMarket", "Afeks furniture fittings"),
    ("0431101", "", r"\bboya", "", "", "paint category"),
    ("0431108", "", r"banyo|tesisat", "", "", "bath and plumbing category"),
    ("0431109", "", r"yalitim|yapi kimyasal|yapistirici|insaat malzeme|insaat ve izolasyon|seramik ve insaat", "", "", "building materials category"),
    ("0431102", "", r"parke", "", "", "flooring category"),
    ("0721302", "", r"\boto\b|otomotiv", "", "", "auto category"),
    ("0511111", "", r"karyola", "", "", "bed frame category"),
    ("0511111", "", r"^ (yatak|yataklar) $", "", "", "plain bed category"),
    ("0511116", "", r"portmanto|vestiyer|ayakkabilik|\bantre\b", "", "", "hall furniture category"),
    ("0511117", "", r"kahve kosesi", "", "", "coffee corner category"),
    ("0921204", "", r"yilbasi|\bnoel\b", "", "", "Christmas category"),
    ("1321105", "", r"duvar saati|\bsaatler?\b", "", "", "clock category"),
    ("0511115", "", r"\bofis\b|calisma (masa|alani)", "", "", "office furniture category"),
    ("0540104", "", r"\bsofra\b|sunum", "", "", "tableware category"),
    ("0974009", "", r"kirtasiye", "", "", "stationery category"),
    ("0922103", "", r"spor ve outdoor|kamp malzeme|kamp kapcilik|kamp mutfagi|spor outdoor", "", "", "sports category"),
    ("0321102", "", r"ayak koruyucu", "", "", "safety footwear category"),
    (WORK_SAFETY, "", r"is guvenli|goz koruyucu|solunum|maske|uyari levha", "", "", "work safety category"),
    ("0721302", "", r"tekne ve karavan|karavan", "", "", "boat and caravan category"),
    ("0321102", "", r"koruyucu ayakkabi", "", "", "protective footwear category"),
    (FITTINGS, "", r"elektrik", "", "", "electrical category"),
    (LIGHTING, "", r"aydinlatma", "", "", "lighting category"),
    (GARDEN, "", r"bahce", "", "", "garden category"),
    (FITTINGS, "", r"hirdavat|nalbur|baglanti|yapi market", r"el alet|makina|makine", "", "hardware category"),
    (TOOLS, "", r"el alet|makina|makine|kaynak|olcu|olcum|kesme|matkap|testere|zimpara|taslama|vidalama|kirici|anahtar|tornavida|pense|guc aktarim|jenerator", "",
     CONSTRUCTION, "tools category"),


    ("0521208", "", r"nevresim|yatak takim|uyku seti|carsaf", "", "", "bed linen category"),
    ("0521204", "", r"yorgan", "", "", "duvet category"),
    ("0521209", "", r"yastik", "", "", "pillow category"),
    ("0521206", "", r"battaniye", "", "", "blanket category"),
    ("0521307", "", r"havlu|bornoz", "", "", "towel category"),
    ("0521101", "", r"\bperde", "", "", "curtain category"),
    ("0511401", "", r"\bhali|kilim", "", "", "carpet category"),
    ("0521207", "", r"\bpike", "", "", "pique category"),
    ("0521905", "", r"masa ortu|mutfak tekstil|kirlent", "", "", "other textile category"),
    ("0540301", "", r"mutfak gerec|servis gerec|pisirme|icecek hazirlama|saklama", "", "", "kitchen utensil category"),
    (DECOR, "", r"dekorasyon", "", "", "decor category"),
    ("0511117", "", r"yemek masasi takim|yemek odasi", "", "", "dining set category"),
    ("0511111", "", r"yataklar|yatak ve baza", "", "", "bed category"),
    ("0511116", "", r"\braflar\b|oturma odasi|kanepe|koltuk", "", "", "living room category"),
    ("0521101", "", r"perde (borulari|aksesuar)", "", "", "curtain rail category"),

]
