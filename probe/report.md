# Veritone-Probe 0.3 – Report

- Zeitpunkt: 2026-10-02 11:41:52
- base_url: https://crxextapi.pd.dmh.veritone.com/assets-api
- Referenz-Clip: 60228265
- Identifier: DEFA05341
- Kollektionen in collections.json: 11

**Übersicht**

- 1. Anmeldung: **OK**
- 2. Referenz-Clip: **OK**
- 3. Feldnamen: **OK**
- 4. Gegenprobe mit dem Clip: **FEHLER**
- 5. Kurzprüfung collections.json: **UNKLAR**
- 6. Vorschlag für Marathon: **UNKLAR**

## 1. Anmeldung – OK


| Methode | HTTP | totalCount | Fehler | Rohdaten |
|---|---|---|---|---|
| query | 200 | 28754 | – | 001_auth_query.json |
| bearer | 200 | 28754 | – | 002_auth_bearer.json |

Verwendet für alle weiteren Abfragen: **query** (query = api_key-Parameter, bearer = Authorization-Header).

## 2. Referenz-Clip – OK


| Quelle | Pfad | HTTP | Felder | Fehler | Rohdaten |
|---|---|---|---|---|---|
| clip | /v1/clip/60228265 | 200 | 1540 | – | 003_clip_clip.json |
| clipDetail | /v1/clip/60228265/clipDetail | 200 | 113 | – | 004_clip_clipDetail.json |
| byIds | /v1/clip/byIds | 200 | 1540 | – | 005_clip_byIds.json |
| assetInfo | /v1/assetInfo/view/clip/60228265/collection/0 | 401 | 0 | Unauthorized | 006_clip_assetInfo.json |

assetInfo ist ein Versuch mit Eltern-Kollektion 0, da die Kollektion des Clips unbekannt ist.

**ID-Felder der Antworten**

| Quelle | Pfad | Wert |
|---|---|---|
| clip | id | 60228265 |
| clip | clipData[0].id | 2843198458 |
| clip | clipData[0].clipId | 60228265 |
| clip | clipData[1].id | 2843198459 |
| clip | clipData[1].clipId | 60228265 |
| clip | clipData[2].id | 2843198460 |
| clip | clipData[2].clipId | 60228265 |
| clip | clipData[3].id | 2843198461 |
| clip | clipData[3].clipId | 60228265 |
| clip | clipData[4].id | 2843198462 |
| clip | clipData[4].clipId | 60228265 |
| clip | clipData[5].id | 2843198463 |
| clip | clipData[5].clipId | 60228265 |
| clip | clipData[6].id | 2843198464 |
| clip | clipData[6].clipId | 60228265 |
| clip | clipData[7].id | 2843198465 |
| clip | clipData[7].clipId | 60228265 |
| clip | clipData[8].id | 2843198466 |
| clip | clipData[8].clipId | 60228265 |
| clip | clipData[9].id | 2843198467 |
| clip | clipData[9].clipId | 60228265 |
| clip | clipData[10].id | 2843198468 |
| clip | clipData[10].clipId | 60228265 |
| clip | clipData[11].id | 2843198469 |
| clip | clipData[11].clipId | 60228265 |
| clip | clipData[12].id | 2843198470 |
| clip | clipData[12].clipId | 60228265 |
| clip | clipData[13].id | 2843198471 |
| clip | clipData[13].clipId | 60228265 |
| clip | clipData[14].id | 2843198472 |
| clip | clipData[14].clipId | 60228265 |
| clip | clipData[15].id | 2843198473 |
| clip | clipData[15].clipId | 60228265 |
| clip | clipData[16].id | 2843198474 |
| clip | clipData[16].clipId | 60228265 |
| clip | clipData[17].id | 2843198475 |
| clip | clipData[17].clipId | 60228265 |
| clip | clipData[18].id | 2843198476 |
| clip | clipData[18].clipId | 60228265 |
| clip | clipData[19].id | 2843198477 |
| clip | clipData[19].clipId | 60228265 |
| clip | clipData[20].id | 2843198478 |
| clip | clipData[20].clipId | 60228265 |
| clip | clipData[21].id | 2843198479 |
| clip | clipData[21].clipId | 60228265 |
| clip | clipData[22].id | 2843198480 |
| clip | clipData[22].clipId | 60228265 |
| clip | clipData[23].id | 2843198481 |
| clip | clipData[23].clipId | 60228265 |
| clip | clipData[24].id | 2843198482 |
| clip | clipData[24].clipId | 60228265 |
| clip | clipData[25].id | 2843198483 |
| clip | clipData[25].clipId | 60228265 |
| clip | clipData[26].id | 2843198484 |
| clip | clipData[26].clipId | 60228265 |
| clip | clipData[27].id | 2843198485 |
| clip | clipData[27].clipId | 60228265 |
| clip | clipData[28].id | 2843198486 |
| clip | clipData[28].clipId | 60228265 |
| clip | clipData[29].id | 2843198487 |
| clip | clipData[29].clipId | 60228265 |
| clip | clipData[30].id | 2843198488 |
| clip | clipData[30].clipId | 60228265 |
| clip | clipData[31].id | 2843198489 |
| clip | clipData[31].clipId | 60228265 |
| clip | clipData[32].id | 2843198490 |
| clip | clipData[32].clipId | 60228265 |
| clip | clipData[33].id | 2843198491 |
| clip | clipData[33].clipId | 60228265 |
| clip | clipData[34].id | 2843198492 |
| clip | clipData[34].clipId | 60228265 |
| clip | clipData[35].id | 2843198493 |
| clip | clipData[35].clipId | 60228265 |
| clip | clipData[36].id | 2843198494 |
| clip | clipData[36].clipId | 60228265 |
| clip | clipData[37].id | 2843198495 |
| clip | clipData[37].clipId | 60228265 |
| clip | clipData[38].id | 2843198496 |
| clip | clipData[38].clipId | 60228265 |
| clip | clipData[39].id | 2843198497 |
| clip | clipData[39].clipId | 60228265 |
| clip | clipData[40].id | 2843198498 |
| clip | clipData[40].clipId | 60228265 |
| clip | clipData[41].id | 2843198499 |
| clip | clipData[41].clipId | 60228265 |
| clip | clipData[42].id | 2843198500 |
| clip | clipData[42].clipId | 60228265 |
| clip | clipData[43].id | 2843198501 |
| clip | clipData[43].clipId | 60228265 |
| clip | clipData[44].id | 2843198502 |
| clip | clipData[44].clipId | 60228265 |
| clip | clipData[45].id | 2843198503 |
| clip | clipData[45].clipId | 60228265 |
| clip | clipData[46].id | 2843198504 |
| clip | clipData[46].clipId | 60228265 |
| clip | clipData[47].id | 2843198505 |
| clip | clipData[47].clipId | 60228265 |
| clip | clipData[48].id | 2843198506 |
| clip | clipData[48].clipId | 60228265 |
| clip | clipData[49].id | 2843198507 |
| clip | clipData[49].clipId | 60228265 |
| clip | clipData[50].id | 2843198508 |
| clip | clipData[50].clipId | 60228265 |
| clip | clipData[51].id | 2843198509 |
| clip | clipData[51].clipId | 60228265 |
| clip | clipData[52].id | 2843198510 |
| clip | clipData[52].clipId | 60228265 |
| clip | clipData[53].id | 2843198511 |
| clip | clipData[53].clipId | 60228265 |
| clip | clipData[54].id | 2843198512 |
| clip | clipData[54].clipId | 60228265 |
| clip | clipData[55].id | 2843198513 |
| clip | clipData[55].clipId | 60228265 |
| clip | clipData[56].id | 2843198514 |
| clip | clipData[56].clipId | 60228265 |
| clip | clipData[57].id | 2843198515 |
| clip | clipData[57].clipId | 60228265 |
| clip | clipData[58].id | 2843198516 |
| clip | clipData[58].clipId | 60228265 |
| clip | clipData[59].id | 2843198517 |
| clip | clipData[59].clipId | 60228265 |
| clip | clipData[60].id | 2843198518 |
| clip | clipData[60].clipId | 60228265 |
| clip | clipData[61].id | 2843198519 |
| clip | clipData[61].clipId | 60228265 |
| clip | clipData[62].id | 2843198520 |
| clip | clipData[62].clipId | 60228265 |
| clip | clipData[63].id | 2843198521 |
| clip | clipData[63].clipId | 60228265 |
| clip | clipData[64].id | 2843198522 |
| clip | clipData[64].clipId | 60228265 |
| clip | clipData[65].id | 2843198523 |
| clip | clipData[65].clipId | 60228265 |
| clip | clipData[66].id | 2843198524 |
| clip | clipData[66].clipId | 60228265 |
| clip | clipData[67].id | 2843198525 |
| clip | clipData[67].clipId | 60228265 |
| clip | clipData[68].id | 2843198526 |
| clip | clipData[68].clipId | 60228265 |
| clip | clipData[69].id | 2843198527 |
| clip | clipData[69].clipId | 60228265 |
| clip | clipData[70].id | 2843198528 |
| clip | clipData[70].clipId | 60228265 |
| clip | clipData[71].id | 2843198529 |
| clip | clipData[71].clipId | 60228265 |
| clip | clipData[72].id | 2843198530 |
| clip | clipData[72].clipId | 60228265 |
| clip | clipData[73].id | 2843198531 |
| clip | clipData[73].clipId | 60228265 |
| clip | clipData[74].id | 2843198532 |
| clip | clipData[74].clipId | 60228265 |
| clip | clipData[75].id | 2843198533 |
| clip | clipData[75].clipId | 60228265 |
| clip | clipData[76].id | 2843198534 |
| clip | clipData[76].clipId | 60228265 |
| clip | clipData[77].id | 2843198535 |
| clip | clipData[77].clipId | 60228265 |
| clip | clipData[78].id | 2843198536 |
| clip | clipData[78].clipId | 60228265 |
| clip | clipData[79].id | 2843198538 |
| clip | clipData[79].clipId | 60228265 |
| clip | clipData[80].id | 2843198539 |
| clip | clipData[80].clipId | 60228265 |
| clip | clipData[81].id | 2843198540 |
| clip | clipData[81].clipId | 60228265 |
| clip | clipData[82].id | 2843198541 |
| clip | clipData[82].clipId | 60228265 |
| clip | clipData[83].id | 2843198542 |
| clip | clipData[83].clipId | 60228265 |
| clip | clipData[84].id | 2843198543 |
| clip | clipData[84].clipId | 60228265 |
| clip | clipData[85].id | 2843198545 |
| clip | clipData[85].clipId | 60228265 |
| clip | clipData[86].id | 2843198546 |
| clip | clipData[86].clipId | 60228265 |
| clip | clipData[87].id | 2843198547 |
| clip | clipData[87].clipId | 60228265 |
| clip | clipData[88].id | 2843198548 |
| clip | clipData[88].clipId | 60228265 |
| clip | clipData[89].id | 2843198549 |
| clip | clipData[89].clipId | 60228265 |
| clip | clipData[90].id | 2843198550 |
| clip | clipData[90].clipId | 60228265 |
| clip | clipData[91].id | 2843198551 |
| clip | clipData[91].clipId | 60228265 |
| clip | clipData[92].id | 2843198552 |
| clip | clipData[92].clipId | 60228265 |
| clip | clipData[93].id | 2843198553 |
| clip | clipData[93].clipId | 60228265 |
| clip | clipData[94].id | 2843198554 |
| clip | clipData[94].clipId | 60228265 |
| clip | clipData[95].id | 2843198555 |
| clip | clipData[95].clipId | 60228265 |
| clip | clipData[96].id | 2843198556 |
| clip | clipData[96].clipId | 60228265 |
| clip | clipData[97].id | 2843198557 |
| clip | clipData[97].clipId | 60228265 |
| clip | clipData[98].id | 2843198558 |
| clip | clipData[98].clipId | 60228265 |
| clip | clipData[99].id | 2843198559 |
| clip | clipData[99].clipId | 60228265 |
| clip | clipData[100].id | 2843198560 |
| clip | clipData[100].clipId | 60228265 |
| clip | clipData[101].id | 2843198561 |
| clip | clipData[101].clipId | 60228265 |
| clip | clipData[102].id | 2843198562 |
| clip | clipData[102].clipId | 60228265 |
| clip | clipData[103].id | 2843198563 |
| clip | clipData[103].clipId | 60228265 |
| clip | clipData[104].id | 2843198564 |
| clip | clipData[104].clipId | 60228265 |
| clip | clipData[105].id | 2843198565 |
| clip | clipData[105].clipId | 60228265 |
| clip | clipData[106].id | 2843198566 |
| clip | clipData[106].clipId | 60228265 |
| clip | clipData[107].id | 2843198567 |
| clip | clipData[107].clipId | 60228265 |
| clip | clipData[108].id | 2843198568 |
| clip | clipData[108].clipId | 60228265 |
| clip | clipData[109].id | 2843198569 |
| clip | clipData[109].clipId | 60228265 |
| clip | clipData[110].id | 2843198570 |
| clip | clipData[110].clipId | 60228265 |
| clip | clipData[111].id | 2843198571 |
| clip | clipData[111].clipId | 60228265 |
| clip | clipData[112].id | 2843198572 |
| clip | clipData[112].clipId | 60228265 |
| clip | clipData[113].id | 2843198573 |
| clip | clipData[113].clipId | 60228265 |
| clip | clipData[114].id | 2843198574 |
| clip | clipData[114].clipId | 60228265 |
| clip | clipData[115].id | 2843198575 |
| clip | clipData[115].clipId | 60228265 |
| clip | clipData[116].id | 2843198576 |
| clip | clipData[116].clipId | 60228265 |
| clip | clipData[117].id | 2843198577 |
| clip | clipData[117].clipId | 60228265 |
| clip | clipData[118].id | 2843198578 |
| clip | clipData[118].clipId | 60228265 |
| clip | clipData[119].id | 2843198581 |
| clip | clipData[119].clipId | 60228265 |
| clip | clipData[120].id | 2843198582 |
| clip | clipData[120].clipId | 60228265 |
| clip | clipData[121].id | 2843198583 |
| clip | clipData[121].clipId | 60228265 |
| clip | clipData[122].id | 2843198584 |
| clip | clipData[122].clipId | 60228265 |
| clip | clipData[123].id | 2843198585 |
| clip | clipData[123].clipId | 60228265 |
| clip | clipData[124].id | 2843198586 |
| clip | clipData[124].clipId | 60228265 |
| clip | clipData[125].id | 2843198587 |
| clip | clipData[125].clipId | 60228265 |
| clip | clipData[126].id | 2843198588 |
| clip | clipData[126].clipId | 60228265 |
| clip | clipData[127].id | 2843198589 |
| clip | clipData[127].clipId | 60228265 |
| clip | clipData[128].id | 2843198845 |
| clip | clipData[128].clipId | 60228265 |
| clip | clipData[129].id | 2843198846 |
| clip | clipData[129].clipId | 60228265 |
| clip | clipData[130].id | 2843198847 |
| clip | clipData[130].clipId | 60228265 |
| clip | clipData[131].id | 2843198848 |
| clip | clipData[131].clipId | 60228265 |
| clip | clipData[132].id | 2843198849 |
| clip | clipData[132].clipId | 60228265 |
| clip | clipData[133].id | 2843198855 |
| clip | clipData[133].clipId | 60228265 |
| clip | clipData[134].id | 2843198856 |
| clip | clipData[134].clipId | 60228265 |
| clip | clipData[135].id | 2843198857 |
| clip | clipData[135].clipId | 60228265 |
| clip | clipData[136].id | 2843198858 |
| clip | clipData[136].clipId | 60228265 |
| clip | clipData[137].id | 2843198859 |
| clip | clipData[137].clipId | 60228265 |
| clip | clipData[138].id | 2843198860 |
| clip | clipData[138].clipId | 60228265 |
| clip | clipData[139].id | 2843198861 |
| clip | clipData[139].clipId | 60228265 |
| clip | clipData[140].id | 2843198862 |
| clip | clipData[140].clipId | 60228265 |
| clip | clipData[141].id | 2843198863 |
| clip | clipData[141].clipId | 60228265 |
| clip | clipData[142].id | 2843198864 |
| clip | clipData[142].clipId | 60228265 |
| clip | clipData[143].id | 2843198865 |
| clip | clipData[143].clipId | 60228265 |
| clip | clipData[144].id | 2843198866 |
| clip | clipData[144].clipId | 60228265 |
| clip | clipData[145].id | 2843198867 |
| clip | clipData[145].clipId | 60228265 |
| clip | clipData[146].id | 2843198868 |
| clip | clipData[146].clipId | 60228265 |
| clip | clipData[147].id | 2843198869 |
| clip | clipData[147].clipId | 60228265 |
| clip | clipData[148].id | 2843198870 |
| clip | clipData[148].clipId | 60228265 |
| clip | clipData[149].id | 2843198871 |
| clip | clipData[149].clipId | 60228265 |
| clip | clipData[150].id | 2843198872 |
| clip | clipData[150].clipId | 60228265 |
| clip | clipData[151].id | 2843198873 |
| clip | clipData[151].clipId | 60228265 |
| clip | clipData[152].id | 2843198874 |
| clip | clipData[152].clipId | 60228265 |
| clip | clipData[153].id | 2843198875 |
| clip | clipData[153].clipId | 60228265 |
| clip | clipData[154].id | 2843198876 |
| clip | clipData[154].clipId | 60228265 |
| clip | clipData[155].id | 2843198877 |
| clip | clipData[155].clipId | 60228265 |
| clip | clipData[156].id | 2843198878 |
| clip | clipData[156].clipId | 60228265 |
| clip | clipData[157].id | 2843198879 |
| clip | clipData[157].clipId | 60228265 |
| clip | clipData[158].id | 2843198880 |
| clip | clipData[158].clipId | 60228265 |
| clip | clipData[159].id | 2843198881 |
| clip | clipData[159].clipId | 60228265 |
| clip | clipData[160].id | 2843198882 |
| clip | clipData[160].clipId | 60228265 |
| clip | clipData[161].id | 2843198883 |
| clip | clipData[161].clipId | 60228265 |
| clip | clipData[162].id | 2843198884 |
| clip | clipData[162].clipId | 60228265 |
| clip | clipData[163].id | 2843198885 |
| clip | clipData[163].clipId | 60228265 |
| clip | clipData[164].id | 2843198886 |
| clip | clipData[164].clipId | 60228265 |
| clip | clipData[165].id | 2843198887 |
| clip | clipData[165].clipId | 60228265 |
| clip | clipData[166].id | 2843198889 |
| clip | clipData[166].clipId | 60228265 |
| clip | clipData[167].id | 2843198890 |
| clip | clipData[167].clipId | 60228265 |
| clip | clipData[168].id | 2843198959 |
| clip | clipData[168].clipId | 60228265 |
| clip | clipData[169].id | 2843200168 |
| clip | clipData[169].clipId | 60228265 |
| clip | clipData[170].id | 2843200169 |
| clip | clipData[170].clipId | 60228265 |
| clip | clipData[171].id | 2843200170 |
| clip | clipData[171].clipId | 60228265 |
| clip | clipData[172].id | 2843200171 |
| clip | clipData[172].clipId | 60228265 |
| clip | clipData[173].id | 2843200174 |
| clip | clipData[173].clipId | 60228265 |
| clip | clipData[174].id | 2843200210 |
| clip | clipData[174].clipId | 60228265 |
| clip | clipData[175].id | 2843200211 |
| clip | clipData[175].clipId | 60228265 |
| clip | clipData[176].id | 2843200212 |
| clip | clipData[176].clipId | 60228265 |
| clip | clipData[177].id | 2843621656 |
| clip | clipData[177].clipId | 60228265 |
| clip | clipData[178].id | 2843621756 |
| clip | clipData[178].clipId | 60228265 |
| clip | clipData[179].id | 2843621757 |
| clip | clipData[179].clipId | 60228265 |
| clip | clipData[180].id | 2843621758 |
| clip | clipData[180].clipId | 60228265 |
| clip | clipData[181].id | 2843621759 |
| clip | clipData[181].clipId | 60228265 |
| clip | clipData[182].id | 2843621760 |
| clip | clipData[182].clipId | 60228265 |
| clip | clipData[183].id | 2843621761 |
| clip | clipData[183].clipId | 60228265 |
| clip | clipData[184].id | 2843621762 |
| clip | clipData[184].clipId | 60228265 |
| clip | clipData[185].id | 2843621763 |
| clip | clipData[185].clipId | 60228265 |
| clip | clipData[186].id | 2843621764 |
| clip | clipData[186].clipId | 60228265 |
| clip | clipData[187].id | 2843621765 |
| clip | clipData[187].clipId | 60228265 |
| clip | clipData[188].id | 2843621766 |
| clip | clipData[188].clipId | 60228265 |
| clip | clipData[189].id | 2843621767 |
| clip | clipData[189].clipId | 60228265 |
| clip | clipData[190].id | 2843621768 |
| clip | clipData[190].clipId | 60228265 |
| clip | clipData[191].id | 2843621769 |
| clip | clipData[191].clipId | 60228265 |
| clip | clipData[192].id | 2843621770 |
| clip | clipData[192].clipId | 60228265 |
| clip | clipData[193].id | 2843621771 |
| clip | clipData[193].clipId | 60228265 |
| clip | clipData[194].id | 2843621772 |
| clip | clipData[194].clipId | 60228265 |
| clip | clipData[195].id | 2843621773 |
| clip | clipData[195].clipId | 60228265 |
| clip | clipData[196].id | 2843621774 |
| clip | clipData[196].clipId | 60228265 |
| clip | clipData[197].id | 2843621775 |
| clip | clipData[197].clipId | 60228265 |
| clip | clipData[198].id | 2843621776 |
| clip | clipData[198].clipId | 60228265 |
| clip | clipData[199].id | 2843621777 |
| clip | clipData[199].clipId | 60228265 |
| clip | clipData[200].id | 2843621778 |
| clip | clipData[200].clipId | 60228265 |
| clip | clipData[201].id | 2843621779 |
| clip | clipData[201].clipId | 60228265 |
| clip | clipData[202].id | 2843621780 |
| clip | clipData[202].clipId | 60228265 |
| clip | clipData[203].id | 2843621781 |
| clip | clipData[203].clipId | 60228265 |
| clip | clipData[204].id | 2843621782 |
| clip | clipData[204].clipId | 60228265 |
| clip | clipData[205].id | 2843621783 |
| clip | clipData[205].clipId | 60228265 |
| clip | clipData[206].id | 2843621784 |
| clip | clipData[206].clipId | 60228265 |
| clip | clipData[207].id | 2843621785 |
| clip | clipData[207].clipId | 60228265 |
| clip | clipData[208].id | 2843621786 |
| clip | clipData[208].clipId | 60228265 |
| clip | clipData[209].id | 2843621787 |
| clip | clipData[209].clipId | 60228265 |
| clip | clipData[210].id | 2843621788 |
| clip | clipData[210].clipId | 60228265 |
| clip | clipData[211].id | 2843621789 |
| clip | clipData[211].clipId | 60228265 |
| clip | clipData[212].id | 2843621790 |
| clip | clipData[212].clipId | 60228265 |
| clip | clipData[213].id | 2843621791 |
| clip | clipData[213].clipId | 60228265 |
| clip | clipData[214].id | 2843621792 |
| clip | clipData[214].clipId | 60228265 |
| clip | clipData[215].id | 2843621793 |
| clip | clipData[215].clipId | 60228265 |
| clip | clipData[216].id | 2843621794 |
| clip | clipData[216].clipId | 60228265 |
| clip | clipData[217].id | 2843621795 |
| clip | clipData[217].clipId | 60228265 |
| clip | clipData[218].id | 2843621796 |
| clip | clipData[218].clipId | 60228265 |
| clip | clipData[219].id | 2843621797 |
| clip | clipData[219].clipId | 60228265 |
| clip | clipData[220].id | 2843621798 |
| clip | clipData[220].clipId | 60228265 |
| clip | clipData[221].id | 2843621799 |
| clip | clipData[221].clipId | 60228265 |
| clip | clipData[222].id | 2843621800 |
| clip | clipData[222].clipId | 60228265 |
| clip | clipData[223].id | 2843621801 |
| clip | clipData[223].clipId | 60228265 |
| clip | clipData[224].id | 2843621802 |
| clip | clipData[224].clipId | 60228265 |
| clip | clipData[225].id | 2843621803 |
| clip | clipData[225].clipId | 60228265 |
| clip | clipData[226].id | 2843621804 |
| clip | clipData[226].clipId | 60228265 |
| clip | clipData[227].id | 2843621805 |
| clip | clipData[227].clipId | 60228265 |
| clip | clipData[228].id | 2843621806 |
| clip | clipData[228].clipId | 60228265 |
| clip | clipData[229].id | 2843621807 |
| clip | clipData[229].clipId | 60228265 |
| clip | clipData[230].id | 2843621808 |
| clip | clipData[230].clipId | 60228265 |
| clip | clipData[231].id | 2843621809 |
| clip | clipData[231].clipId | 60228265 |
| clip | clipData[232].id | 2843621810 |
| clip | clipData[232].clipId | 60228265 |
| clip | clipData[233].id | 2843621811 |
| clip | clipData[233].clipId | 60228265 |
| clip | clipData[234].id | 2843621812 |
| clip | clipData[234].clipId | 60228265 |
| clip | clipData[235].id | 2843621813 |
| clip | clipData[235].clipId | 60228265 |
| clip | clipData[236].id | 2843621814 |
| clip | clipData[236].clipId | 60228265 |
| clip | clipData[237].id | 2843621815 |
| clip | clipData[237].clipId | 60228265 |
| clip | clipData[238].id | 2843621816 |
| clip | clipData[238].clipId | 60228265 |
| clip | clipData[239].id | 2843621817 |
| clip | clipData[239].clipId | 60228265 |
| clip | clipData[240].id | 2843621818 |
| clip | clipData[240].clipId | 60228265 |
| clip | clipData[241].id | 2843621819 |
| clip | clipData[241].clipId | 60228265 |
| clip | clipData[242].id | 2843621820 |
| clip | clipData[242].clipId | 60228265 |
| clip | clipData[243].id | 2843621821 |
| clip | clipData[243].clipId | 60228265 |
| clip | clipData[244].id | 2843621822 |
| clip | clipData[244].clipId | 60228265 |
| clip | clipData[245].id | 2843621823 |
| clip | clipData[245].clipId | 60228265 |
| clip | clipData[246].id | 2843621824 |
| clip | clipData[246].clipId | 60228265 |
| clip | clipData[247].id | 2843621825 |
| clip | clipData[247].clipId | 60228265 |
| clip | clipData[248].id | 2843621826 |
| clip | clipData[248].clipId | 60228265 |
| clip | clipData[249].id | 2843621827 |
| clip | clipData[249].clipId | 60228265 |
| clip | clipData[250].id | 2843621828 |
| clip | clipData[250].clipId | 60228265 |
| clip | clipData[251].id | 2843621829 |
| clip | clipData[251].clipId | 60228265 |
| clip | clipData[252].id | 2843621830 |
| clip | clipData[252].clipId | 60228265 |
| clip | clipData[253].id | 2843621831 |
| clip | clipData[253].clipId | 60228265 |
| clip | clipData[254].id | 2843621832 |
| clip | clipData[254].clipId | 60228265 |
| clip | clipData[255].id | 2843621833 |
| clip | clipData[255].clipId | 60228265 |
| clip | clipData[256].id | 2843621834 |
| clip | clipData[256].clipId | 60228265 |
| clip | clipData[257].id | 2843621835 |
| clip | clipData[257].clipId | 60228265 |
| clip | clipData[258].id | 2843621836 |
| clip | clipData[258].clipId | 60228265 |
| clip | clipData[259].id | 2843621837 |
| clip | clipData[259].clipId | 60228265 |
| clip | clipData[260].id | 2843621838 |
| clip | clipData[260].clipId | 60228265 |
| clip | clipData[261].id | 2843621839 |
| clip | clipData[261].clipId | 60228265 |
| clip | clipData[262].id | 2843621840 |
| clip | clipData[262].clipId | 60228265 |
| clip | clipData[263].id | 2843621841 |
| clip | clipData[263].clipId | 60228265 |
| clip | clipData[264].id | 2843621842 |
| clip | clipData[264].clipId | 60228265 |
| clip | clipData[265].id | 2843621948 |
| clip | clipData[265].clipId | 60228265 |
| clip | clipData[266].id | 3758538157 |
| clip | clipData[266].clipId | 60228265 |
| clip | clipData[267].id | 3758538158 |
| clip | clipData[267].clipId | 60228265 |
| clip | clipData[268].id | 3758538159 |
| clip | clipData[268].clipId | 60228265 |
| clip | renditions[0].id | 131042592 |
| clip | renditions[0].clipId | 60228265 |
| clip | renditions[1].id | 131042593 |
| clip | renditions[1].clipId | 60228265 |
| clip | renditions[2].id | 131042607 |
| clip | renditions[2].clipId | 60228265 |
| clip | renditions[3].id | 131042608 |
| clip | renditions[3].clipId | 60228265 |
| clip | renditions[4].id | 131042609 |
| clip | renditions[4].clipId | 60228265 |
| clip | renditions[5].id | 131042630 |
| clip | renditions[5].clipId | 60228265 |
| clip | renditions[6].id | 131042633 |
| clip | renditions[6].clipId | 60228265 |
| clip | renditions[7].id | 131042637 |
| clip | renditions[7].clipId | 60228265 |
| clip | renditions[8].id | 131042638 |
| clip | renditions[8].clipId | 60228265 |
| clip | renditions[9].id | 131042639 |
| clip | renditions[9].clipId | 60228265 |
| clip | renditions[10].id | 131042677 |
| clip | renditions[10].clipId | 60228265 |
| clip | supplier.id | 31637981 |
| clipDetail | assetId | 60228265 |
| clipDetail | detailTypeMap.id | 299 |
| byIds | list[0].id | 60228265 |

Asset-ID aus der Web-Adresse = Clip-ID: **ja**

**Vollständige Feldliste** (gleiche Feld/Wert-Paare zusammengefasst)

| Feld | Wert | Fundstellen |
|---|---|---|
| id | 60228265 | clip: id; clipDetail: detailTypeMap.common[0]<id>; byIds: list[0].id |
| family | screener | clip: family; clipDetail: detailTypeMap.common[1]<family>; byIds: list[0].family |
| ingested | 2025-07-15T12:56:16Z | clip: ingested; byIds: list[0].ingested |
| liveDate | 2025-07-15T12:56:17Z | clip: liveDate; byIds: list[0].liveDate |
| modified | 2026-09-21T12:27:04Z | clip: modified; byIds: list[0].modified |
| name | 1RVF3C_JBCE3SSZRS | clip: name; clipDetail: detailTypeMap.common[5]<name>; byIds: list[0].name |
| SI.Resource.Modified | 20260921122704 | clip: clipData[0]<SI.Resource.Modified>; byIds: list[0].clipData[0]<SI.Resource.Modified> |
| id | 2843198458 | clip: clipData[0].id; byIds: list[0].clipData[0].id |
| clipId | 60228265 | clip: clipData[0].clipId; clip: clipData[1].clipId; clip: clipData[2].clipId (+557) |
| inherited | false | clip: clipData[0].inherited; clip: clipData[1].inherited; clip: clipData[2].inherited (+535) |
| modified | 2026-09-21T12:27:05Z | clip: clipData[0].modified; clip: clipData[78].modified; clip: clipData[174].modified (+11) |
| Resource.Family | screener | clip: clipData[1]<Resource.Family>; clipDetail: detailTypeMap.primary[2]<Resource.Family>; byIds: list[0].clipData[1]<R… |
| id | 2843198459 | clip: clipData[1].id; byIds: list[0].clipData[1].id |
| modified | 2025-07-15T12:56:19Z | clip: clipData[1].modified; clip: clipData[83].modified; clip: clipData[94].modified (+25) |
| Resource.Class | Footage | clip: clipData[2]<Resource.Class>; clipDetail: detailTypeMap.primary[0]<Resource.Class>; clipDetail: metaDataDefault[1]… |
| id | 2843198460 | clip: clipData[2].id; byIds: list[0].clipData[2].id |
| modified | 2025-07-15T12:56:16Z | clip: clipData[2].modified; clip: clipData[3].modified; clip: clipData[4].modified (+143) |
| Audio.Notes | Yes | clip: clipData[3]<Audio.Notes>; clipDetail: detailTypeMap.primary[11]<Audio.Notes>; byIds: list[0].clipData[3]<Audio.No… |
| id | 2843198461 | clip: clipData[3].id; byIds: list[0].clipData[3].id |
| DMH.Notes2 | 781285 | clip: clipData[4]<DMH.Notes2>; byIds: list[0].clipData[4]<DMH.Notes2> |
| id | 2843198462 | clip: clipData[4].id; byIds: list[0].clipData[4].id |
| Description | 1. Millionen Juden klagen an\nDer "Augenzeuge" besuchte den größten Jüdischen Friedhof Deutschlands in Berlin-Weißensee… | clip: clipData[5]<Description>; byIds: list[0].clipData[5]<Description> |
| id | 2843198463 | clip: clipData[5].id; byIds: list[0].clipData[5].id |
| Description.DE | 1. Millionen Juden klagen an\nDer "Augenzeuge" besuchte den größten Jüdischen Friedhof Deutschlands in Berlin-Weißensee… | clip: clipData[6]<Description.DE>; clipDetail: detailTypeMap.primary[12]<Description.DE>; clipDetail: detailTypeMap.sec… |
| id | 2843198464 | clip: clipData[6].id; byIds: list[0].clipData[6].id |
| Description.Date | 1964 | clip: clipData[7]<Description.Date>; clipDetail: detailTypeMap.primary[6]<Description.Date>; byIds: list[0].clipData[7]… |
| id | 2843198465 | clip: clipData[7].id; byIds: list[0].clipData[7].id |
| Description.EN | 1. million Jews on trial\nThe "Eyewitness" visited Germany's largest Jewish cemetery in Berlin-Weißensee and reports on… | clip: clipData[8]<Description.EN>; clipDetail: detailTypeMap.primary[13]<Description.EN>; clipDetail: detailTypeMap.sec… |
| id | 2843198466 | clip: clipData[8].id; byIds: list[0].clipData[8].id |
| Description.FR | 1. Accuser des millions de Juifs\nLe "témoin oculaire" a visité le plus grand cimetière juif d'Allemagne à Berlin-Weiße… | clip: clipData[9]<Description.FR>; byIds: list[0].clipData[9]<Description.FR> |
| id | 2843198467 | clip: clipData[9].id; byIds: list[0].clipData[9].id |
| Keywords.DE | Religion; Katholizismus; Papst; Judentum; Gericht; Baudenkmal; Jüdischer Friedhof; Kuba; Luftverkehr; Warschau; Hochhau… | clip: clipData[10]<Keywords.DE>; clipDetail: detailTypeMap.secondary[0].content_details.data[2].section[0]<Keywords.DE>… |
| id | 2843198468 | clip: clipData[10].id; byIds: list[0].clipData[10].id |
| Keywords.EN | Religion; Catholicism; Pope; Judaism; Court; Monument; Jewish cemetery; Cuba; Air traffic; Warsaw; Skyscraper; City; Ca… | clip: clipData[11]<Keywords.EN>; clipDetail: detailTypeMap.secondary[0].content_details.data[2].section[1]<Keywords.EN>… |
| id | 2843198469 | clip: clipData[11].id; byIds: list[0].clipData[11].id |
| Keywords.FR | Catholicisme ; Cuba ; Catholicisme ; Cimetière juif ; Chat ; Juif ; Cour de justice ; Monument aux morts ; Varsovie ; B… | clip: clipData[12]<Keywords.FR>; byIds: list[0].clipData[12]<Keywords.FR> |
| id | 2843198470 | clip: clipData[12].id; byIds: list[0].clipData[12].id |
| Production.Accounting.ArticleRange | P0001 | clip: clipData[13]<Production.Accounting.ArticleRange>; byIds: list[0].clipData[13]<Production.Accounting.ArticleRange> |
| id | 2843198471 | clip: clipData[13].id; byIds: list[0].clipData[13].id |
| Production.Accounting.License | 93044 | clip: clipData[14]<Production.Accounting.License>; byIds: list[0].clipData[14]<Production.Accounting.License> |
| id | 2843198472 | clip: clipData[14].id; byIds: list[0].clipData[14].id |
| Production.AspectRatio | 1.9:1 | clip: clipData[15]<Production.AspectRatio>; byIds: list[0].clipData[15]<Production.AspectRatio> |
| id | 2843198473 | clip: clipData[15].id; byIds: list[0].clipData[15].id |
| Production.AudioBitDepth | 24 | clip: clipData[16]<Production.AudioBitDepth>; byIds: list[0].clipData[16]<Production.AudioBitDepth> |
| id | 2843198474 | clip: clipData[16].id; byIds: list[0].clipData[16].id |
| Production.AudioSampleRate | 48000 | clip: clipData[17]<Production.AudioSampleRate>; byIds: list[0].clipData[17]<Production.AudioSampleRate> |
| id | 2843198475 | clip: clipData[17].id; byIds: list[0].clipData[17].id |
| Production.ClosedCaption | No | clip: clipData[18]<Production.ClosedCaption>; byIds: list[0].clipData[18]<Production.ClosedCaption> |
| id | 2843198476 | clip: clipData[18].id; byIds: list[0].clipData[18].id |
| Production.Codec | DNxHR HQX 10bit | clip: clipData[19]<Production.Codec>; byIds: list[0].clipData[19]<Production.Codec> |
| id | 2843198477 | clip: clipData[19].id; byIds: list[0].clipData[19].id |
| Production.Cognition.FaceRecognition | No | clip: clipData[20]<Production.Cognition.FaceRecognition>; byIds: list[0].clipData[20]<Production.Cognition.FaceRecognit… |
| id | 2843198478 | clip: clipData[20].id; byIds: list[0].clipData[20].id |
| Production.Cognition.SpeakerSeperation | No | clip: clipData[21]<Production.Cognition.SpeakerSeperation>; byIds: list[0].clipData[21]<Production.Cognition.SpeakerSep… |
| id | 2843198479 | clip: clipData[21].id; byIds: list[0].clipData[21].id |
| Production.Cognition.TextRecognition | No | clip: clipData[22]<Production.Cognition.TextRecognition>; byIds: list[0].clipData[22]<Production.Cognition.TextRecognit… |
| id | 2843198480 | clip: clipData[22].id; byIds: list[0].clipData[22].id |
| Production.CountryOfOrigin.DE | Deutsche Demokratische Republik (DDR) | clip: clipData[23]<Production.CountryOfOrigin.DE>; clipDetail: detailTypeMap.secondary[0].content_details.data[1].secti… |
| id | 2843198481 | clip: clipData[23].id; byIds: list[0].clipData[23].id |
| Production.CountryOfOrigin.EN | Germany (East) | clip: clipData[24]<Production.CountryOfOrigin.EN>; clipDetail: detailTypeMap.secondary[0].content_details.data[1].secti… |
| id | 2843198482 | clip: clipData[24].id; byIds: list[0].clipData[24].id |
| Production.CountryOfOrigin.FR | Allemagne (Est) | clip: clipData[25]<Production.CountryOfOrigin.FR>; byIds: list[0].clipData[25]<Production.CountryOfOrigin.FR> |
| id | 2843198483 | clip: clipData[25].id; byIds: list[0].clipData[25].id |
| Production.DEFA | e6dbe764-c00a-ee11-8f6e-000d3aabc8c4 | clip: clipData[26]<Production.DEFA>; byIds: list[0].clipData[26]<Production.DEFA> |
| id | 2843198484 | clip: clipData[26].id; byIds: list[0].clipData[26].id |
| Production.Edit.Cleanfeed | No | clip: clipData[27]<Production.Edit.Cleanfeed>; byIds: list[0].clipData[27]<Production.Edit.Cleanfeed> |
| id | 2843198485 | clip: clipData[27].id; byIds: list[0].clipData[27].id |
| Production.Edit.Color | No | clip: clipData[28]<Production.Edit.Color>; clipDetail: detailTypeMap.primary[10]<Production.Edit.Color>; byIds: list[0]… |
| id | 2843198486 | clip: clipData[28].id; byIds: list[0].clipData[28].id |
| Production.Edit.Digitized | Yes | clip: clipData[29]<Production.Edit.Digitized>; clipDetail: detailTypeMap.secondary[0].technical_details.data[0].section… |
| id | 2843198487 | clip: clipData[29].id; byIds: list[0].clipData[29].id |
| Production.Format | Video | clip: clipData[30]<Production.Format>; clipDetail: detailTypeMap.secondary[0].technical_details.data[0].section[0]<Prod… |
| id | 2843198488 | clip: clipData[30].id; byIds: list[0].clipData[30].id |
| Production.Format.Digitized | 35mm | clip: clipData[31]<Production.Format.Digitized>; byIds: list[0].clipData[31]<Production.Format.Digitized> |
| id | 2843198489 | clip: clipData[31].id; byIds: list[0].clipData[31].id |
| Production.Format.Original | 35mm | clip: clipData[32]<Production.Format.Original>; byIds: list[0].clipData[32]<Production.Format.Original> |
| id | 2843198490 | clip: clipData[32].id; byIds: list[0].clipData[32].id |
| Production.FrameRate | 24/1 | clip: clipData[33]<Production.FrameRate>; byIds: list[0].clipData[33]<Production.FrameRate> |
| id | 2843198491 | clip: clipData[33].id; byIds: list[0].clipData[33].id |
| Production.Genre.DE | Wochenschau | clip: clipData[34]<Production.Genre.DE>; clipDetail: detailTypeMap.secondary[0].content_details.data[0].section[7]<Prod… |
| id | 2843198492 | clip: clipData[34].id; byIds: list[0].clipData[34].id |
| Production.Genre.EN | Newsreel | clip: clipData[35]<Production.Genre.EN>; clipDetail: detailTypeMap.secondary[0].content_details.data[0].section[8]<Prod… |
| id | 2843198493 | clip: clipData[35].id; byIds: list[0].clipData[35].id |
| Production.Genre.FR | Film d'actualité | clip: clipData[36]<Production.Genre.FR>; byIds: list[0].clipData[36]<Production.Genre.FR> |
| id | 2843198494 | clip: clipData[36].id; byIds: list[0].clipData[36].id |
| Production.Language.Original.DE | Deutsch | clip: clipData[37]<Production.Language.Original.DE>; clipDetail: detailTypeMap.secondary[0].content_details.data[2].sec… |
| id | 2843198495 | clip: clipData[37].id; byIds: list[0].clipData[37].id |
| Production.Language.Original.EN | German | clip: clipData[38]<Production.Language.Original.EN>; clipDetail: detailTypeMap.secondary[0].content_details.data[2].sec… |
| id | 2843198496 | clip: clipData[38].id; byIds: list[0].clipData[38].id |
| Production.Language.Original.FR | allemand | clip: clipData[39]<Production.Language.Original.FR>; byIds: list[0].clipData[39]<Production.Language.Original.FR> |
| id | 2843198497 | clip: clipData[39].id; byIds: list[0].clipData[39].id |
| Production.Language.Subtitle | No | clip: clipData[40]<Production.Language.Subtitle>; byIds: list[0].clipData[40]<Production.Language.Subtitle> |
| id | 2843198498 | clip: clipData[40].id; byIds: list[0].clipData[40].id |
| Production.Narrator | true | clip: clipData[41]<Production.Narrator>; byIds: list[0].clipData[41]<Production.Narrator> |
| id | 2843198499 | clip: clipData[41].id; byIds: list[0].clipData[41].id |
| Production.Resolution | 4096x2160 | clip: clipData[42]<Production.Resolution>; byIds: list[0].clipData[42]<Production.Resolution> |
| id | 2843198500 | clip: clipData[42].id; byIds: list[0].clipData[42].id |
| Production.Shoot.Decade | 1960 | clip: clipData[43]<Production.Shoot.Decade>; clipDetail: detailTypeMap.secondary[0].content_details.data[0].section[3]<… |
| id | 2843198501 | clip: clipData[43].id; byIds: list[0].clipData[43].id |
| Production.Shoot.Year | 1964 | clip: clipData[44]<Production.Shoot.Year>; clipDetail: detailTypeMap.primary[7]<Production.Shoot.Year>; byIds: list[0].… |
| id | 2843198502 | clip: clipData[44].id; byIds: list[0].clipData[44].id |
| Production.Shotlist.DE | 1. Jüdischer Friedhof Berlin / Weißensee: Kameraschwenk über Gräber; verschiedene Grabsteine sind zu sehen; Denkmal für… | clip: clipData[45]<Production.Shotlist.DE>; clipDetail: detailTypeMap.secondary[0].content_details.data[2].section[7]<P… |
| id | 2843198503 | clip: clipData[45].id; byIds: list[0].clipData[45].id |
| Production.Shotlist.EN | 1. Jewish Cemetery Berlin / Weißensee: Camera panning over graves; various gravestones can be seen; Monument to the Jew… | clip: clipData[46]<Production.Shotlist.EN>; clipDetail: detailTypeMap.secondary[0].content_details.data[2].section[8]<P… |
| id | 2843198504 | clip: clipData[46].id; byIds: list[0].clipData[46].id |
| Production.Shotlist.FR | 1. cimetière juif de Berlin / Weißensee : travelling sur des tombes ; on voit différentes pierres tombales ; monument a… | clip: clipData[47]<Production.Shotlist.FR>; byIds: list[0].clipData[47]<Production.Shotlist.FR> |
| id | 2843198505 | clip: clipData[47].id; byIds: list[0].clipData[47].id |
| Production.Studio.DE | DEFA-Studio für Wochenschau und Dokumentarfilme | clip: clipData[48]<Production.Studio.DE>; clipDetail: detailTypeMap.secondary[0].cast_crew.data[1].section[0]<Productio… |
| id | 2843198506 | clip: clipData[48].id; byIds: list[0].clipData[48].id |
| Production.Studio.EN | DEFA studio for newsreel and documentary films | clip: clipData[49]<Production.Studio.EN>; clipDetail: detailTypeMap.secondary[0].cast_crew.data[1].section[1]<Productio… |
| id | 2843198507 | clip: clipData[49].id; byIds: list[0].clipData[49].id |
| Production.Studio.FR | DEFA-Studio für Wochenschau und Dokumentarfilme (Studio DEFA pour les actualités et les documentaires) | clip: clipData[50]<Production.Studio.FR>; byIds: list[0].clipData[50]<Production.Studio.FR> |
| id | 2843198508 | clip: clipData[50].id; byIds: list[0].clipData[50].id |
| Production.Subtitle | No | clip: clipData[51]<Production.Subtitle>; byIds: list[0].clipData[51]<Production.Subtitle> |
| id | 2843198509 | clip: clipData[51].id; byIds: list[0].clipData[51].id |
| Production.Subtitle.Curated | No | clip: clipData[52]<Production.Subtitle.Curated>; byIds: list[0].clipData[52]<Production.Subtitle.Curated> |
| id | 2843198510 | clip: clipData[52].id; byIds: list[0].clipData[52].id |
| Production.Talent.Cast.Extras.DE | Josef Schwarz | clip: clipData[53]<Production.Talent.Cast.Extras.DE>; clipDetail: detailTypeMap.secondary[0].content_details.data[2].se… |
| id | 2843198511 | clip: clipData[53].id; byIds: list[0].clipData[53].id |
| Production.Talent.Cast.Extras.EN | Josef Schwarz | clip: clipData[54]<Production.Talent.Cast.Extras.EN>; clipDetail: detailTypeMap.secondary[0].content_details.data[2].se… |
| id | 2843198512 | clip: clipData[54].id; byIds: list[0].clipData[54].id |
| Production.Talent.Cast.Extras.FR | Josef Schwarz | clip: clipData[55]<Production.Talent.Cast.Extras.FR>; byIds: list[0].clipData[55]<Production.Talent.Cast.Extras.FR> |
| id | 2843198513 | clip: clipData[55].id; byIds: list[0].clipData[55].id |
| Production.Talent.Cast.Principals.DE | Giovanni Battista Enrico Antonio Maria Montini (Papst Paul VI.) | clip: clipData[56]<Production.Talent.Cast.Principals.DE>; clipDetail: detailTypeMap.secondary[0].content_details.data[2… |
| id | 2843198514 | clip: clipData[56].id; byIds: list[0].clipData[56].id |
| Production.Talent.Cast.Principals.EN | Giovanni Battista Enrico Antonio Maria Montini (Pope Paul VI) | clip: clipData[57]<Production.Talent.Cast.Principals.EN>; clipDetail: detailTypeMap.secondary[0].content_details.data[2… |
| id | 2843198515 | clip: clipData[57].id; byIds: list[0].clipData[57].id |
| Production.Talent.Cast.Principals.FR | Giovanni Battista Enrico Antonio Maria Montini (Pape Paul VI) | clip: clipData[58]<Production.Talent.Cast.Principals.FR>; byIds: list[0].clipData[58]<Production.Talent.Cast.Principals… |
| id | 2843198516 | clip: clipData[58].id; byIds: list[0].clipData[58].id |
| Production.User.Id | PROGRESS | clip: clipData[59]<Production.User.Id>; byIds: list[0].clipData[59]<Production.User.Id> |
| id | 2843198517 | clip: clipData[59].id; byIds: list[0].clipData[59].id |
| Rights.Agent | DEFA | clip: clipData[60]<Rights.Agent>; byIds: list[0].clipData[60]<Rights.Agent> |
| id | 2843198518 | clip: clipData[60].id; byIds: list[0].clipData[60].id |
| Supplier.Barcode | DEFA05341 | clip: clipData[61]<Supplier.Barcode>; clipDetail: detailTypeMap.primary[4]<Supplier.Barcode>; byIds: list[0].clipData[6… |
| id | 2843198519 | clip: clipData[61].id; byIds: list[0].clipData[61].id |
| Supplier.Collection | East German Newsreel "Der Augenzeuge" | clip: clipData[62]<Supplier.Collection>; clipDetail: detailTypeMap.primary[9]<Supplier.Collection>; byIds: list[0].clip… |
| id | 2843198520 | clip: clipData[62].id; byIds: list[0].clipData[62].id |
| Supplier.ParentClip | Q6UJ9A0044FP | clip: clipData[63]<Supplier.ParentClip>; byIds: list[0].clipData[63]<Supplier.ParentClip> |
| id | 2843198521 | clip: clipData[63].id; byIds: list[0].clipData[63].id |
| Supplier.Rights | Rights Managed | clip: clipData[64]<Supplier.Rights>; byIds: list[0].clipData[64]<Supplier.Rights> |
| id | 2843198522 | clip: clipData[64].id; byIds: list[0].clipData[64].id |
| Supplier.Source | DEFA | clip: clipData[65]<Supplier.Source>; clipDetail: detailTypeMap.primary[8]<Supplier.Source>; byIds: list[0].clipData[65]… |
| id | 2843198523 | clip: clipData[65].id; byIds: list[0].clipData[65].id |
| Supplier.Title | Der Augenzeuge 1964/03 | clip: clipData[66]<Supplier.Title>; clipDetail: detailTypeMap.primary[5]<Supplier.Title>; clipDetail: detailTypeMap.sec… |
| id | 2843198524 | clip: clipData[66].id; byIds: list[0].clipData[66].id |
| Supplier.Uuid | d4d88a2d-ca85-4fd1-9b59-dae60c065ccc | clip: clipData[67]<Supplier.Uuid>; byIds: list[0].clipData[67]<Supplier.Uuid> |
| id | 2843198525 | clip: clipData[67].id; byIds: list[0].clipData[67].id |
| TE.OriginalName | s3-vtn-progress-editshare-or-1.s3.amazonaws.com/DEFA05341__Der+Augenzeuge+1964-03.mp4 | clip: clipData[68]<TE.OriginalName>; byIds: list[0].clipData[68]<TE.OriginalName> |
| id | 2843198526 | clip: clipData[68].id; byIds: list[0].clipData[68].id |
| Title | Der Augenzeuge 1964/03 | clip: clipData[69]<Title>; byIds: list[0].clipData[69]<Title> |
| id | 2843198527 | clip: clipData[69].id; byIds: list[0].clipData[69].id |
| Title.DE | Der Augenzeuge 1964/03 | clip: clipData[70]<Title.DE>; clipDetail: detailTypeMap.secondary[0].content_details.data[0].section[1]<Title.DE>; byId… |
| id | 2843198528 | clip: clipData[70].id; byIds: list[0].clipData[70].id |
| Title.EN | Der Augenzeuge 1964/03 | clip: clipData[71]<Title.EN>; clipDetail: detailTypeMap.secondary[0].content_details.data[0].section[2]<Title.EN>; byId… |
| id | 2843198529 | clip: clipData[71].id; byIds: list[0].clipData[71].id |
| Title.FR | Der Augenzeuge 1964/03 | clip: clipData[72]<Title.FR>; byIds: list[0].clipData[72]<Title.FR> |
| id | 2843198530 | clip: clipData[72].id; byIds: list[0].clipData[72].id |
| Transcription.Corrected | No | clip: clipData[73]<Transcription.Corrected>; byIds: list[0].clipData[73]<Transcription.Corrected> |
| id | 2843198531 | clip: clipData[73].id; byIds: list[0].clipData[73].id |
| Transcription.EN | No | clip: clipData[74]<Transcription.EN>; byIds: list[0].clipData[74]<Transcription.EN> |
| id | 2843198532 | clip: clipData[74].id; byIds: list[0].clipData[74].id |
| Workflow.Transcript.Status | true | clip: clipData[75]<Workflow.Transcript.Status>; byIds: list[0].clipData[75]<Workflow.Transcript.Status> |
| id | 2843198533 | clip: clipData[75].id; byIds: list[0].clipData[75].id |
| modified | 2025-07-16T11:30:44Z | clip: clipData[75].modified; clip: clipData[177].modified; byIds: list[0].clipData[75].modified (+1) |
| TE.DigitalFormat | High Definition | clip: clipData[76]<TE.DigitalFormat>; clipDetail: detailTypeMap.primary[1]<TE.DigitalFormat>; clipDetail: metaDataDefau… |
| id | 2843198534 | clip: clipData[76].id; byIds: list[0].clipData[76].id |
| modified | 2025-07-15T12:58:57Z | clip: clipData[76].modified; clip: clipData[133].modified; clip: clipData[134].modified (+65) |
| TE.Priority | 5 | clip: clipData[77]<TE.Priority>; byIds: list[0].clipData[77]<TE.Priority> |
| id | 2843198535 | clip: clipData[77].id; byIds: list[0].clipData[77].id |
| modified | 2025-07-15T12:56:17Z | clip: clipData[77].modified; byIds: list[0].clipData[77].modified |
| TWK.State.History | 2025-07-15 12:56:17 progress-initial --(IsLicensable.DMH != "true")--&gt live;2025-07-15 12:56:17 progress-live.initial… | clip: clipData[78]<TWK.State.History>; byIds: list[0].clipData[78]<TWK.State.History> |
| id | 2843198536 | clip: clipData[78].id; byIds: list[0].clipData[78].id |
| TE.LiveDate | 2025-07-15 12:56:17 | clip: clipData[79]<TE.LiveDate>; byIds: list[0].clipData[79]<TE.LiveDate> |
| id | 2843198538 | clip: clipData[79].id; byIds: list[0].clipData[79].id |
| modified | 2025-07-15T12:56:18Z | clip: clipData[79].modified; clip: clipData[80].modified; clip: clipData[81].modified (+61) |
| SI.Resource.Descriptor | clip_60228265 | clip: clipData[80]<SI.Resource.Descriptor>; byIds: list[0].clipData[80]<SI.Resource.Descriptor> |
| id | 2843198539 | clip: clipData[80].id; byIds: list[0].clipData[80].id |
| SI.Resource.DatabaseId | 60228265 | clip: clipData[81]<SI.Resource.DatabaseId>; byIds: list[0].clipData[81]<SI.Resource.DatabaseId> |
| id | 2843198540 | clip: clipData[81].id; byIds: list[0].clipData[81].id |
| SI.Resource.Name | 1RVF3C_JBCE3SSZRS | clip: clipData[82]<SI.Resource.Name>; byIds: list[0].clipData[82]<SI.Resource.Name> |
| id | 2843198541 | clip: clipData[82].id; byIds: list[0].clipData[82].id |
| SI.Resource.Family | screener | clip: clipData[83]<SI.Resource.Family>; byIds: list[0].clipData[83]<SI.Resource.Family> |
| id | 2843198542 | clip: clipData[83].id; byIds: list[0].clipData[83].id |
| SI.Resource.Created | 20250715125616 | clip: clipData[84]<SI.Resource.Created>; byIds: list[0].clipData[84]<SI.Resource.Created> |
| id | 2843198543 | clip: clipData[84].id; byIds: list[0].clipData[84].id |
| SI.Resource.Type | clip | clip: clipData[85]<SI.Resource.Type>; byIds: list[0].clipData[85]<SI.Resource.Type> |
| id | 2843198545 | clip: clipData[85].id; byIds: list[0].clipData[85].id |
| SI.Description | 1. Millionen Juden klagen an\nDer "Augenzeuge" besuchte den größten Jüdischen Friedhof Deutschlands in Berlin-Weißensee… | clip: clipData[86]<SI.Description>; byIds: list[0].clipData[86]<SI.Description> |
| id | 2843198546 | clip: clipData[86].id; byIds: list[0].clipData[86].id |
| SI.Title | Der Augenzeuge 1964/03 | clip: clipData[87]<SI.Title>; byIds: list[0].clipData[87]<SI.Title> |
| id | 2843198547 | clip: clipData[87].id; byIds: list[0].clipData[87].id |
| SI.Owner | Progress | clip: clipData[88]<SI.Owner>; clipDetail: detailTypeMap.primary[3]<SI.Owner>; byIds: list[0].clipData[88]<SI.Owner> |
| id | 2843198548 | clip: clipData[88].id; byIds: list[0].clipData[88].id |
| SI.Supplier.Tier | 5 | clip: clipData[89]<SI.Supplier.Tier>; byIds: list[0].clipData[89]<SI.Supplier.Tier> |
| id | 2843198549 | clip: clipData[89].id; byIds: list[0].clipData[89].id |
| SI.Supplier.SearchRank.Wazee | 5 | clip: clipData[90]<SI.Supplier.SearchRank.Wazee>; byIds: list[0].clipData[90]<SI.Supplier.SearchRank.Wazee> |
| id | 2843198550 | clip: clipData[90].id; byIds: list[0].clipData[90].id |
| SI.Supplier.CategoryType | Platform | clip: clipData[91]<SI.Supplier.CategoryType>; byIds: list[0].clipData[91]<SI.Supplier.CategoryType> |
| id | 2843198551 | clip: clipData[91].id; byIds: list[0].clipData[91].id |
| SI.Supplier.ContentCategory | Studio | clip: clipData[92]<SI.Supplier.ContentCategory>; byIds: list[0].clipData[92]<SI.Supplier.ContentCategory> |
| id | 2843198552 | clip: clipData[92].id; byIds: list[0].clipData[92].id |
| SI.Renditions | DerAugenzeuge196403mp4 lpf4v lpwmpgovtcf4v ltjpg mcwmpgovtcmp4 mpf4v spwmpgf4v stjpg xpf4v xtjpg | clip: clipData[93]<SI.Renditions>; byIds: list[0].clipData[93]<SI.Renditions> |
| id | 2843198553 | clip: clipData[93].id; byIds: list[0].clipData[93].id |
| modified | 2025-07-15T13:14:05Z | clip: clipData[93].modified; clip: clipData[169].modified; clip: clipData[170].modified (+7) |
| SI.Original.Names | s3-vtn-progress-editshare-or-1.s3.amazonaws.com/DEFA05341__Der+Augenzeuge+1964-03.mp4 DEFA05341__Der+Augenzeuge+1964-03… | clip: clipData[94]<SI.Original.Names>; byIds: list[0].clipData[94]<SI.Original.Names> |
| id | 2843198554 | clip: clipData[94].id; byIds: list[0].clipData[94].id |
| SI.Property.Name | 1RVF3C_JBCE3SSZRS | clip: clipData[95]<SI.Property.Name>; byIds: list[0].clipData[95]<SI.Property.Name> |
| id | 2843198555 | clip: clipData[95].id; byIds: list[0].clipData[95].id |
| SI.Property.Score | 000 | clip: clipData[96]<SI.Property.Score>; byIds: list[0].clipData[96]<SI.Property.Score> |
| id | 2843198556 | clip: clipData[96].id; byIds: list[0].clipData[96].id |
| SI.LicensableNow | false | clip: clipData[97]<SI.LicensableNow>; byIds: list[0].clipData[97]<SI.LicensableNow> |
| id | 2843198557 | clip: clipData[97].id; byIds: list[0].clipData[97].id |
| SI.Media.Physical | None | clip: clipData[98]<SI.Media.Physical>; byIds: list[0].clipData[98]<SI.Media.Physical> |
| id | 2843198558 | clip: clipData[98].id; byIds: list[0].clipData[98].id |
| SI.Rights.Talent | Release Not On File | clip: clipData[99]<SI.Rights.Talent>; byIds: list[0].clipData[99]<SI.Rights.Talent> |
| id | 2843198559 | clip: clipData[99].id; byIds: list[0].clipData[99].id |
| SI.Rights.Trademark | Release Not On File | clip: clipData[100]<SI.Rights.Trademark>; byIds: list[0].clipData[100]<SI.Rights.Trademark> |
| id | 2843198560 | clip: clipData[100].id; byIds: list[0].clipData[100].id |
| SI.Rights.Music | Release Not On File | clip: clipData[101]<SI.Rights.Music>; byIds: list[0].clipData[101]<SI.Rights.Music> |
| id | 2843198561 | clip: clipData[101].id; byIds: list[0].clipData[101].id |
| SI.Rights.SoundFx | Release Not On File | clip: clipData[102]<SI.Rights.SoundFx>; byIds: list[0].clipData[102]<SI.Rights.SoundFx> |
| id | 2843198562 | clip: clipData[102].id; byIds: list[0].clipData[102].id |
| SI.Rights.Voice | Release Not On File | clip: clipData[103]<SI.Rights.Voice>; byIds: list[0].clipData[103]<SI.Rights.Voice> |
| id | 2843198563 | clip: clipData[103].id; byIds: list[0].clipData[103].id |
| SI.Rights.Location | Release Not On File | clip: clipData[104]<SI.Rights.Location>; byIds: list[0].clipData[104]<SI.Rights.Location> |
| id | 2843198564 | clip: clipData[104].id; byIds: list[0].clipData[104].id |
| SI.Price.Class | D | clip: clipData[105]<SI.Price.Class>; byIds: list[0].clipData[105]<SI.Price.Class> |
| id | 2843198565 | clip: clipData[105].id; byIds: list[0].clipData[105].id |
| SI.Resource.Grade | 3 | clip: clipData[106]<SI.Resource.Grade>; byIds: list[0].clipData[106]<SI.Resource.Grade> |
| id | 2843198566 | clip: clipData[106].id; byIds: list[0].clipData[106].id |
| SI.Thesauri | supprogress wazeenet | clip: clipData[107]<SI.Thesauri>; byIds: list[0].clipData[107]<SI.Thesauri> |
| id | 2843198567 | clip: clipData[107].id; byIds: list[0].clipData[107].id |
| SI.SearchRank.Shuffle | 38c3225b954e150f9ab72f7268b05076 | clip: clipData[108]<SI.SearchRank.Shuffle>; byIds: list[0].clipData[108]<SI.SearchRank.Shuffle> |
| id | 2843198568 | clip: clipData[108].id; byIds: list[0].clipData[108].id |
| SI.Supplier.Reference | s3-vtn-progress-editshare-or-1.s3.amazonaws.com/DEFA05341__Der+Augenzeuge+1964-03.mp4 DEFA05341__Der+Augenzeuge+1964-03… | clip: clipData[109]<SI.Supplier.Reference>; byIds: list[0].clipData[109]<SI.Supplier.Reference> |
| id | 2843198569 | clip: clipData[109].id; byIds: list[0].clipData[109].id |
| SI.InWorkflow | true | clip: clipData[110]<SI.InWorkflow>; byIds: list[0].clipData[110]<SI.InWorkflow> |
| id | 2843198570 | clip: clipData[110].id; byIds: list[0].clipData[110].id |
| modified | 2025-07-15T13:14:48Z | clip: clipData[110].modified; clip: clipData[112].modified; clip: clipData[115].modified (+9) |
| SI.IsHidden | false | clip: clipData[111]<SI.IsHidden>; byIds: list[0].clipData[111]<SI.IsHidden> |
| id | 2843198571 | clip: clipData[111].id; byIds: list[0].clipData[111].id |
| SI.LicensableIn | nowhere | clip: clipData[112]<SI.LicensableIn>; byIds: list[0].clipData[112]<SI.LicensableIn> |
| id | 2843198572 | clip: clipData[112].id; byIds: list[0].clipData[112].id |
| SI.Channels.Public | nowhere | clip: clipData[113]<SI.Channels.Public>; byIds: list[0].clipData[113]<SI.Channels.Public> |
| id | 2843198573 | clip: clipData[113].id; byIds: list[0].clipData[113].id |
| SI.Channels.Protected | nowhere | clip: clipData[114]<SI.Channels.Protected>; byIds: list[0].clipData[114]<SI.Channels.Protected> |
| id | 2843198574 | clip: clipData[114].id; byIds: list[0].clipData[114].id |
| SI.Channels.Private | nowhere | clip: clipData[115]<SI.Channels.Private>; byIds: list[0].clipData[115]<SI.Channels.Private> |
| id | 2843198575 | clip: clipData[115].id; byIds: list[0].clipData[115].id |
| SI.Created.Timestamp | 20250715125616 | clip: clipData[116]<SI.Created.Timestamp>; byIds: list[0].clipData[116]<SI.Created.Timestamp> |
| id | 2843198576 | clip: clipData[116].id; byIds: list[0].clipData[116].id |
| SI.Resource.Family.SortIndex | 2 | clip: clipData[117]<SI.Resource.Family.SortIndex>; byIds: list[0].clipData[117]<SI.Resource.Family.SortIndex> |
| id | 2843198577 | clip: clipData[117].id; byIds: list[0].clipData[117].id |
| SI.Description.Date | 19640101000000 | clip: clipData[118]<SI.Description.Date>; byIds: list[0].clipData[118]<SI.Description.Date> |
| id | 2843198578 | clip: clipData[118].id; byIds: list[0].clipData[118].id |
| SI.Master.Type | S3ViaS3Signed | clip: clipData[119]<SI.Master.Type>; byIds: list[0].clipData[119]<SI.Master.Type> |
| id | 2843198581 | clip: clipData[119].id; byIds: list[0].clipData[119].id |
| SI.Master.Cdn | s3 | clip: clipData[120]<SI.Master.Cdn>; byIds: list[0].clipData[120]<SI.Master.Cdn> |
| id | 2843198582 | clip: clipData[120].id; byIds: list[0].clipData[120].id |
| SI.Master.S3.Bucket | s3-vtn-progress-editshare-or-1 | clip: clipData[121]<SI.Master.S3.Bucket>; byIds: list[0].clipData[121]<SI.Master.S3.Bucket> |
| id | 2843198583 | clip: clipData[121].id; byIds: list[0].clipData[121].id |
| SI.Master.S3.Key | DEFA05341__Der Augenzeuge 1964-03.mp4 | clip: clipData[122]<SI.Master.S3.Key>; byIds: list[0].clipData[122]<SI.Master.S3.Key> |
| id | 2843198584 | clip: clipData[122].id; byIds: list[0].clipData[122].id |
| SI.Master.Location | 81b908cf-4aa4-4a4c-954d-70dbf3a69baa | clip: clipData[123]<SI.Master.Location>; byIds: list[0].clipData[123]<SI.Master.Location> |
| id | 2843198585 | clip: clipData[123].id; byIds: list[0].clipData[123].id |
| SI.Master.Filename | DEFA05341__Der Augenzeuge 1964-03.mp4 | clip: clipData[124]<SI.Master.Filename>; byIds: list[0].clipData[124]<SI.Master.Filename> |
| id | 2843198586 | clip: clipData[124].id; byIds: list[0].clipData[124].id |
| SI.Master.Extension | mp4 | clip: clipData[125]<SI.Master.Extension>; byIds: list[0].clipData[125]<SI.Master.Extension> |
| id | 2843198587 | clip: clipData[125].id; byIds: list[0].clipData[125].id |
| SI.Master.FileSize | 110932480 | clip: clipData[126]<SI.Master.FileSize>; byIds: list[0].clipData[126]<SI.Master.FileSize> |
| id | 2843198588 | clip: clipData[126].id; byIds: list[0].clipData[126].id |
| SI.Master.SourceReference | 2025-07-15 12:55:12 | clip: clipData[127]<SI.Master.SourceReference>; byIds: list[0].clipData[127]<SI.Master.SourceReference> |
| id | 2843198589 | clip: clipData[127].id; byIds: list[0].clipData[127].id |
| TWK.Hold | true | clip: clipData[128]<TWK.Hold>; byIds: list[0].clipData[128]<TWK.Hold> |
| id | 2843198845 | clip: clipData[128].id; byIds: list[0].clipData[128].id |
| modified | 2025-07-15T12:58:24Z | clip: clipData[128].modified; clip: clipData[129].modified; clip: clipData[130].modified (+7) |
| Topic.Discovery | German | clip: clipData[129]<Topic.Discovery>; byIds: list[0].clipData[129]<Topic.Discovery> |
| id | 2843198846 | clip: clipData[129].id; byIds: list[0].clipData[129].id |
| Rights.Reproduction | Rights Managed | clip: clipData[130]<Rights.Reproduction>; clipDetail: detailTypeMap.common[8]<Rights.Reproduction>; clipDetail: metaDat… |
| id | 2843198847 | clip: clipData[130].id; byIds: list[0].clipData[130].id |
| TWK.DataSync | true | clip: clipData[131]<TWK.DataSync>; byIds: list[0].clipData[131]<TWK.DataSync> |
| id | 2843198848 | clip: clipData[131].id; byIds: list[0].clipData[131].id |
| TWK.CreateRenditions | ,lp,lt,st,sp,mc,xp,xt, | clip: clipData[132]<TWK.CreateRenditions>; byIds: list[0].clipData[132]<TWK.CreateRenditions> |
| id | 2843198849 | clip: clipData[132].id; byIds: list[0].clipData[132].id |
| Format.BroadcastStandard | 2K | clip: clipData[133]<Format.BroadcastStandard>; byIds: list[0].clipData[133]<Format.BroadcastStandard> |
| id | 2843198855 | clip: clipData[133].id; byIds: list[0].clipData[133].id |
| Format.Audio.Codec | aac | clip: clipData[134]<Format.Audio.Codec>; byIds: list[0].clipData[134]<Format.Audio.Codec> |
| id | 2843198856 | clip: clipData[134].id; byIds: list[0].clipData[134].id |
| Format.ScanType | Progressive | clip: clipData[135]<Format.ScanType>; byIds: list[0].clipData[135]<Format.ScanType> |
| id | 2843198857 | clip: clipData[135].id; byIds: list[0].clipData[135].id |
| Format.ImageDataRate | 1.20 Mbps | clip: clipData[136]<Format.ImageDataRate>; byIds: list[0].clipData[136]<Format.ImageDataRate> |
| id | 2843198858 | clip: clipData[136].id; byIds: list[0].clipData[136].id |
| Format.ChromaFormat | 4:2:0 | clip: clipData[137]<Format.ChromaFormat>; byIds: list[0].clipData[137]<Format.ChromaFormat> |
| id | 2843198859 | clip: clipData[137].id; byIds: list[0].clipData[137].id |
| Format.Video.Level | 51 | clip: clipData[138]<Format.Video.Level>; byIds: list[0].clipData[138]<Format.Video.Level> |
| id | 2843198860 | clip: clipData[138].id; byIds: list[0].clipData[138].id |
| Format.Video.Profile | Main | clip: clipData[139]<Format.Video.Profile>; byIds: list[0].clipData[139]<Format.Video.Profile> |
| id | 2843198861 | clip: clipData[139].id; byIds: list[0].clipData[139].id |
| Format.QuickTime.Parser | ffprobe | clip: clipData[140]<Format.QuickTime.Parser>; byIds: list[0].clipData[140]<Format.QuickTime.Parser> |
| id | 2843198862 | clip: clipData[140].id; byIds: list[0].clipData[140].id |
| Format.FrameRate | 24 fps | clip: clipData[141]<Format.FrameRate>; clipDetail: detailTypeMap.common[6]<Format.FrameRate>; clipDetail: metaDataDefau… |
| id | 2843198863 | clip: clipData[141].id; byIds: list[0].clipData[141].id |
| Format.Duration | 639625 | clip: clipData[142]<Format.Duration>; clipDetail: detailTypeMap.common[7]<Format.Duration>; clipDetail: metaDataDefault… |
| id | 2843198864 | clip: clipData[142].id; byIds: list[0].clipData[142].id |
| Format.FileSize | 105 MB | clip: clipData[143]<Format.FileSize>; byIds: list[0].clipData[143]<Format.FileSize> |
| id | 2843198865 | clip: clipData[143].id; byIds: list[0].clipData[143].id |
| Format.TimecodeTrack.DropFrame | false | clip: clipData[144]<Format.TimecodeTrack.DropFrame>; byIds: list[0].clipData[144]<Format.TimecodeTrack.DropFrame> |
| id | 2843198866 | clip: clipData[144].id; byIds: list[0].clipData[144].id |
| Format.ColorModel | bt709 | clip: clipData[145]<Format.ColorModel>; byIds: list[0].clipData[145]<Format.ColorModel> |
| id | 2843198867 | clip: clipData[145].id; byIds: list[0].clipData[145].id |
| Format.AspectRatio | 16:9 | clip: clipData[146]<Format.AspectRatio>; byIds: list[0].clipData[146]<Format.AspectRatio> |
| id | 2843198868 | clip: clipData[146].id; byIds: list[0].clipData[146].id |
| Format.AudioDataRate | 128 Kbps | clip: clipData[147]<Format.AudioDataRate>; byIds: list[0].clipData[147]<Format.AudioDataRate> |
| id | 2843198869 | clip: clipData[147].id; byIds: list[0].clipData[147].id |
| Format.QuickTime.Codec | avc1 | clip: clipData[148]<Format.QuickTime.Codec>; byIds: list[0].clipData[148]<Format.QuickTime.Codec> |
| id | 2843198870 | clip: clipData[148].id; byIds: list[0].clipData[148].id |
| Format.ScanType.ContainsInterlaced | false | clip: clipData[149]<Format.ScanType.ContainsInterlaced>; byIds: list[0].clipData[149]<Format.ScanType.ContainsInterlace… |
| id | 2843198871 | clip: clipData[149].id; byIds: list[0].clipData[149].id |
| Format.MasterStandard | MP4 | clip: clipData[150]<Format.MasterStandard>; byIds: list[0].clipData[150]<Format.MasterStandard> |
| id | 2843198872 | clip: clipData[150].id; byIds: list[0].clipData[150].id |
| Format.ImageChannelConfiguration | 1 | clip: clipData[151]<Format.ImageChannelConfiguration>; byIds: list[0].clipData[151]<Format.ImageChannelConfiguration> |
| id | 2843198873 | clip: clipData[151].id; byIds: list[0].clipData[151].id |
| Format.FieldOrder | Progressive | clip: clipData[152]<Format.FieldOrder>; byIds: list[0].clipData[152]<Format.FieldOrder> |
| id | 2843198874 | clip: clipData[152].id; byIds: list[0].clipData[152].id |
| Format.AudioSamplingRate | 48.0 KHz | clip: clipData[153]<Format.AudioSamplingRate>; byIds: list[0].clipData[153]<Format.AudioSamplingRate> |
| id | 2843198875 | clip: clipData[153].id; byIds: list[0].clipData[153].id |
| Format.FrameRateVariable | false | clip: clipData[154]<Format.FrameRateVariable>; byIds: list[0].clipData[154]<Format.FrameRateVariable> |
| id | 2843198876 | clip: clipData[154].id; byIds: list[0].clipData[154].id |
| Format.TimecodeTrack.Present | true | clip: clipData[155]<Format.TimecodeTrack.Present>; byIds: list[0].clipData[155]<Format.TimecodeTrack.Present> |
| id | 2843198877 | clip: clipData[155].id; byIds: list[0].clipData[155].id |
| Format.TimeStart | 01:00:00:00 | clip: clipData[156]<Format.TimeStart>; clipDetail: metaDataDefault[2]<Format.TimeStart>; byIds: list[0].clipData[156]<F… |
| id | 2843198878 | clip: clipData[156].id; byIds: list[0].clipData[156].id |
| Format.AudioChannelConfiguration | 2 | clip: clipData[157]<Format.AudioChannelConfiguration>; byIds: list[0].clipData[157]<Format.AudioChannelConfiguration> |
| id | 2843198879 | clip: clipData[157].id; byIds: list[0].clipData[157].id |
| Format.BitDepth | 8 bit | clip: clipData[158]<Format.BitDepth>; byIds: list[0].clipData[158]<Format.BitDepth> |
| id | 2843198880 | clip: clipData[158].id; byIds: list[0].clipData[158].id |
| Format.FrameSize | 2048 x 1080 | clip: clipData[159]<Format.FrameSize>; clipDetail: metaDataDefault[3]<Format.FrameSize>; byIds: list[0].clipData[159]<F… |
| id | 2843198881 | clip: clipData[159].id; byIds: list[0].clipData[159].id |
| Format.TimeEnd | 01:10:39:14 | clip: clipData[160]<Format.TimeEnd>; byIds: list[0].clipData[160]<Format.TimeEnd> |
| id | 2843198882 | clip: clipData[160].id; byIds: list[0].clipData[160].id |
| TE.IsUpdate | true | clip: clipData[161]<TE.IsUpdate>; byIds: list[0].clipData[161]<TE.IsUpdate> |
| id | 2843198883 | clip: clipData[161].id; byIds: list[0].clipData[161].id |
| Format.ScanType.Detail | idet frames: 250, tff: 0, bff: 0, prog: 249, undet: 1 | clip: clipData[162]<Format.ScanType.Detail>; byIds: list[0].clipData[162]<Format.ScanType.Detail> |
| id | 2843198884 | clip: clipData[162].id; byIds: list[0].clipData[162].id |
| SI.Format.Duration | 0000639625 | clip: clipData[163]<SI.Format.Duration>; byIds: list[0].clipData[163]<SI.Format.Duration> |
| id | 2843198885 | clip: clipData[163].id; byIds: list[0].clipData[163].id |
| SI.Format.FrameSizeRatio | 0000018963 | clip: clipData[164]<SI.Format.FrameSizeRatio>; byIds: list[0].clipData[164]<SI.Format.FrameSizeRatio> |
| id | 2843198886 | clip: clipData[164].id; byIds: list[0].clipData[164].id |
| SI.Format.FrameRate | 0000240000 | clip: clipData[165]<SI.Format.FrameRate>; byIds: list[0].clipData[165]<SI.Format.FrameRate> |
| id | 2843198887 | clip: clipData[165].id; byIds: list[0].clipData[165].id |
| Format.SpeedviewStart | 00:00:00:00 | clip: clipData[166]<Format.SpeedviewStart>; byIds: list[0].clipData[166]<Format.SpeedviewStart> |
| id | 2843198889 | clip: clipData[166].id; byIds: list[0].clipData[166].id |
| modified | 2025-07-15T12:58:58Z | clip: clipData[166].modified; clip: clipData[167].modified; byIds: list[0].clipData[166].modified (+1) |
| Format.SpeedviewEnd | 00:00:30:00 | clip: clipData[167]<Format.SpeedviewEnd>; byIds: list[0].clipData[167]<Format.SpeedviewEnd> |
| id | 2843198890 | clip: clipData[167].id; byIds: list[0].clipData[167].id |
| TWK.Workflow.Evaluate | nudge ca7eedbd-36c9-417c-beaf-86f04b030dea | clip: clipData[168]<TWK.Workflow.Evaluate>; byIds: list[0].clipData[168]<TWK.Workflow.Evaluate> |
| id | 2843198959 | clip: clipData[168].id; byIds: list[0].clipData[168].id |
| TWK.HasRenditions | Automatic screener 2025-07-15 13:14:05 | clip: clipData[169]<TWK.HasRenditions>; byIds: list[0].clipData[169]<TWK.HasRenditions> |
| id | 2843200168 | clip: clipData[169].id; byIds: list[0].clipData[169].id |
| Commerce.Rendition | Automatic screener 2025-07-15 13:14:05 | clip: clipData[170]<Commerce.Rendition>; byIds: list[0].clipData[170]<Commerce.Rendition> |
| id | 2843200169 | clip: clipData[170].id; byIds: list[0].clipData[170].id |
| IsLicensable.DMH | true | clip: clipData[171]<IsLicensable.DMH>; byIds: list[0].clipData[171]<IsLicensable.DMH> |
| id | 2843200170 | clip: clipData[171].id; byIds: list[0].clipData[171].id |
| TWK.IsLicensable.DMH | true | clip: clipData[172]<TWK.IsLicensable.DMH>; byIds: list[0].clipData[172]<TWK.IsLicensable.DMH> |
| id | 2843200171 | clip: clipData[172].id; byIds: list[0].clipData[172].id |
| Resource.SiteAccess | dmh_public | clip: clipData[173]<Resource.SiteAccess>; byIds: list[0].clipData[173]<Resource.SiteAccess> |
| id | 2843200174 | clip: clipData[173].id; byIds: list[0].clipData[173].id |
| TWK.PurchaseBlock | 2026-09-21 12:27:04 | clip: clipData[174]<TWK.PurchaseBlock>; byIds: list[0].clipData[174]<TWK.PurchaseBlock> |
| id | 2843200210 | clip: clipData[174].id; byIds: list[0].clipData[174].id |
| TWK.SearchBlock | 2026-09-21 12:27:04 | clip: clipData[175]<TWK.SearchBlock>; byIds: list[0].clipData[175]<TWK.SearchBlock> |
| id | 2843200211 | clip: clipData[175].id; byIds: list[0].clipData[175].id |
| TE.ZombieDate | 2025-07-15 13:14:48 | clip: clipData[176]<TE.ZombieDate>; byIds: list[0].clipData[176]<TE.ZombieDate> |
| id | 2843200212 | clip: clipData[176].id; byIds: list[0].clipData[176].id |
| TWK.Cognate.Category | transcription | clip: clipData[177]<TWK.Cognate.Category>; byIds: list[0].clipData[177]<TWK.Cognate.Category> |
| id | 2843621656 | clip: clipData[177].id; byIds: list[0].clipData[177].id |
| AiWare.Report.All.48 | [INF] Production.Studio.DE: Not mapped to an aiWare schema | clip: clipData[178]<AiWare.Report.All.48>; byIds: list[0].clipData[178]<AiWare.Report.All.48> |
| id | 2843621756 | clip: clipData[178].id; byIds: list[0].clipData[178].id |
| modified | 2025-07-16T11:30:58Z | clip: clipData[178].modified; clip: clipData[179].modified; clip: clipData[180].modified (+169) |
| AiWare.Report.All.49 | [INF] Production.Studio.EN: Not mapped to an aiWare schema | clip: clipData[179]<AiWare.Report.All.49>; byIds: list[0].clipData[179]<AiWare.Report.All.49> |
| id | 2843621757 | clip: clipData[179].id; byIds: list[0].clipData[179].id |
| AiWare.Report.All.46 | [INF] Production.Shotlist.EN: Not mapped to an aiWare schema | clip: clipData[180]<AiWare.Report.All.46>; byIds: list[0].clipData[180]<AiWare.Report.All.46> |
| id | 2843621758 | clip: clipData[180].id; byIds: list[0].clipData[180].id |
| AiWare.Report.All.47 | [INF] Production.Shotlist.FR: Not mapped to an aiWare schema | clip: clipData[181]<AiWare.Report.All.47>; byIds: list[0].clipData[181]<AiWare.Report.All.47> |
| id | 2843621759 | clip: clipData[181].id; byIds: list[0].clipData[181].id |
| AiWare.Report.All.11 | [INF] Keywords.FR: Not mapped to an aiWare schema | clip: clipData[182]<AiWare.Report.All.11>; byIds: list[0].clipData[182]<AiWare.Report.All.11> |
| id | 2843621760 | clip: clipData[182].id; byIds: list[0].clipData[182].id |
| AiWare.Report.All.55 | [INF] Production.Talent.Cast.Extras.FR: Not mapped to an aiWare schema | clip: clipData[183]<AiWare.Report.All.55>; byIds: list[0].clipData[183]<AiWare.Report.All.55> |
| id | 2843621761 | clip: clipData[183].id; byIds: list[0].clipData[183].id |
| AiWare.Report.All.12 | [INF] Owner: Not mapped to an aiWare schema | clip: clipData[184]<AiWare.Report.All.12>; byIds: list[0].clipData[184]<AiWare.Report.All.12> |
| id | 2843621762 | clip: clipData[184].id; byIds: list[0].clipData[184].id |
| AiWare.Report.All.56 | [INF] Production.Talent.Cast.Principals.DE: Not mapped to an aiWare schema | clip: clipData[185]<AiWare.Report.All.56>; byIds: list[0].clipData[185]<AiWare.Report.All.56> |
| id | 2843621763 | clip: clipData[185].id; byIds: list[0].clipData[185].id |
| AiWare.Report.All.53 | [INF] Production.Talent.Cast.Extras.DE: Not mapped to an aiWare schema | clip: clipData[186]<AiWare.Report.All.53>; byIds: list[0].clipData[186]<AiWare.Report.All.53> |
| id | 2843621764 | clip: clipData[186].id; byIds: list[0].clipData[186].id |
| AiWare.Report.All.10 | [INF] Keywords.EN: Not mapped to an aiWare schema | clip: clipData[187]<AiWare.Report.All.10>; byIds: list[0].clipData[187]<AiWare.Report.All.10> |
| id | 2843621765 | clip: clipData[187].id; byIds: list[0].clipData[187].id |
| AiWare.Report.All.54 | [INF] Production.Talent.Cast.Extras.EN: Not mapped to an aiWare schema | clip: clipData[188]<AiWare.Report.All.54>; byIds: list[0].clipData[188]<AiWare.Report.All.54> |
| id | 2843621766 | clip: clipData[188].id; byIds: list[0].clipData[188].id |
| AiWare.Report.All.51 | [INF] Production.Subtitle: Not mapped to an aiWare schema | clip: clipData[189]<AiWare.Report.All.51>; byIds: list[0].clipData[189]<AiWare.Report.All.51> |
| id | 2843621767 | clip: clipData[189].id; byIds: list[0].clipData[189].id |
| AiWare.Report.All.52 | [INF] Production.Subtitle.Curated: Not mapped to an aiWare schema | clip: clipData[190]<AiWare.Report.All.52>; byIds: list[0].clipData[190]<AiWare.Report.All.52> |
| id | 2843621768 | clip: clipData[190].id; byIds: list[0].clipData[190].id |
| AiWare.Report.All.50 | [INF] Production.Studio.FR: Not mapped to an aiWare schema | clip: clipData[191]<AiWare.Report.All.50>; byIds: list[0].clipData[191]<AiWare.Report.All.50> |
| id | 2843621769 | clip: clipData[191].id; byIds: list[0].clipData[191].id |
| AiWare.Report.All.39 | [INF] Production.Language.Original.FR: Not mapped to an aiWare schema | clip: clipData[192]<AiWare.Report.All.39>; byIds: list[0].clipData[192]<AiWare.Report.All.39> |
| id | 2843621770 | clip: clipData[192].id; byIds: list[0].clipData[192].id |
| AiWare.Report.All.37 | [INF] Production.Language.Original.DE: Not mapped to an aiWare schema | clip: clipData[193]<AiWare.Report.All.37>; byIds: list[0].clipData[193]<AiWare.Report.All.37> |
| id | 2843621771 | clip: clipData[193].id; byIds: list[0].clipData[193].id |
| AiWare.Report.All.38 | [INF] Production.Language.Original.EN: Not mapped to an aiWare schema | clip: clipData[194]<AiWare.Report.All.38>; byIds: list[0].clipData[194]<AiWare.Report.All.38> |
| id | 2843621772 | clip: clipData[194].id; byIds: list[0].clipData[194].id |
| AiWare.Report.All.35 | [INF] Production.Genre.EN: Not mapped to an aiWare schema | clip: clipData[195]<AiWare.Report.All.35>; byIds: list[0].clipData[195]<AiWare.Report.All.35> |
| id | 2843621773 | clip: clipData[195].id; byIds: list[0].clipData[195].id |
| AiWare.Report.All.79 | [INF] https://s3-t3m-previewpriv-or-1.s3.us-west-2.amazonaws.com/1RV/F3C/1RVF3C_JBCE3SSZRS_lp.f4v: Asset created | clip: clipData[196]<AiWare.Report.All.79>; byIds: list[0].clipData[196]<AiWare.Report.All.79> |
| id | 2843621774 | clip: clipData[196].id; byIds: list[0].clipData[196].id |
| AiWare.Report.All.36 | [INF] Production.Genre.FR: Not mapped to an aiWare schema | clip: clipData[197]<AiWare.Report.All.36>; byIds: list[0].clipData[197]<AiWare.Report.All.36> |
| id | 2843621775 | clip: clipData[197].id; byIds: list[0].clipData[197].id |
| AiWare.Report.All.44 | [INF] Production.Shoot.Year: Not mapped to an aiWare schema | clip: clipData[198]<AiWare.Report.All.44>; byIds: list[0].clipData[198]<AiWare.Report.All.44> |
| id | 2843621776 | clip: clipData[198].id; byIds: list[0].clipData[198].id |
| AiWare.Report.All.45 | [INF] Production.Shotlist.DE: Not mapped to an aiWare schema | clip: clipData[199]<AiWare.Report.All.45>; byIds: list[0].clipData[199]<AiWare.Report.All.45> |
| id | 2843621777 | clip: clipData[199].id; byIds: list[0].clipData[199].id |
| AiWare.Report.All.42 | [INF] Production.Resolution: Not mapped to an aiWare schema | clip: clipData[200]<AiWare.Report.All.42>; byIds: list[0].clipData[200]<AiWare.Report.All.42> |
| id | 2843621778 | clip: clipData[200].id; byIds: list[0].clipData[200].id |
| AiWare.Report.All.43 | [INF] Production.Shoot.Decade: Not mapped to an aiWare schema | clip: clipData[201]<AiWare.Report.All.43>; byIds: list[0].clipData[201]<AiWare.Report.All.43> |
| id | 2843621779 | clip: clipData[201].id; byIds: list[0].clipData[201].id |
| AiWare.Report.All.40 | [INF] Production.Language.Subtitle: Not mapped to an aiWare schema | clip: clipData[202]<AiWare.Report.All.40>; byIds: list[0].clipData[202]<AiWare.Report.All.40> |
| id | 2843621780 | clip: clipData[202].id; byIds: list[0].clipData[202].id |
| AiWare.Report.All.84 | [INF] https://cdnt3m-a.akamaihd.net/tem/warehouse/1RV/F3C/1RVF3C_JBCE3SSZRS_xt.jpg: Asset created | clip: clipData[203]<AiWare.Report.All.84>; byIds: list[0].clipData[203]<AiWare.Report.All.84> |
| id | 2843621781 | clip: clipData[203].id; byIds: list[0].clipData[203].id |
| AiWare.Report.All.41 | [INF] Production.Narrator: Not mapped to an aiWare schema | clip: clipData[204]<AiWare.Report.All.41>; byIds: list[0].clipData[204]<AiWare.Report.All.41> |
| id | 2843621782 | clip: clipData[204].id; byIds: list[0].clipData[204].id |
| AiWare.Report.All.85 | [INF] https://s3-t3m-compsfast-or-2.s3.us-west-2.amazonaws.com/1RV/F3C/1RVF3C_JBCE3SSZRS_mc-wmpg%2Covtc.mp4: Asset crea… | clip: clipData[205]<AiWare.Report.All.85>; byIds: list[0].clipData[205]<AiWare.Report.All.85> |
| id | 2843621783 | clip: clipData[205].id; byIds: list[0].clipData[205].id |
| AiWare.Report.All.82 | [INF] https://s3-vtn-progress-editshare-or-1.s3.us-west-2.amazonaws.com/DEFA05341__Der%20Augenzeuge%201964-03.mp4: Asse… | clip: clipData[206]<AiWare.Report.All.82>; byIds: list[0].clipData[206]<AiWare.Report.All.82> |
| id | 2843621784 | clip: clipData[206].id; byIds: list[0].clipData[206].id |
| AiWare.Report.All.83 | [INF] https://s3-t3m-previewpriv-or-1.s3.us-west-2.amazonaws.com/1RV/985/1RV985_001_lp.f4v: Asset created | clip: clipData[207]<AiWare.Report.All.83>; byIds: list[0].clipData[207]<AiWare.Report.All.83> |
| id | 2843621785 | clip: clipData[207].id; byIds: list[0].clipData[207].id |
| AiWare.Report.All.80 | [INF] https://s3-t3m-previewpriv-or-1.s3.us-west-2.amazonaws.com/1RV/F3C/1RVF3C_JBCE3SSZRS_sp-wmpg.f4v: Asset created | clip: clipData[208]<AiWare.Report.All.80>; byIds: list[0].clipData[208]<AiWare.Report.All.80> |
| id | 2843621786 | clip: clipData[208].id; byIds: list[0].clipData[208].id |
| AiWare.Report.All.81 | [INF] https://cdnt3m-a.akamaihd.net/tem/warehouse/1RV/F3C/1RVF3C_JBCE3SSZRS_st.jpg: Asset created | clip: clipData[209]<AiWare.Report.All.81>; byIds: list[0].clipData[209]<AiWare.Report.All.81> |
| id | 2843621787 | clip: clipData[209].id; byIds: list[0].clipData[209].id |
| AiWare.TDO.SyncTime | 2025-07-16 11:30:45 | clip: clipData[210]<AiWare.TDO.SyncTime>; byIds: list[0].clipData[210]<AiWare.TDO.SyncTime> |
| id | 2843621788 | clip: clipData[210].id; byIds: list[0].clipData[210].id |
| AiWare.Report.All.28 | [INF] Production.Edit.Color: Not mapped to an aiWare schema | clip: clipData[211]<AiWare.Report.All.28>; byIds: list[0].clipData[211]<AiWare.Report.All.28> |
| id | 2843621789 | clip: clipData[211].id; byIds: list[0].clipData[211].id |
| AiWare.Report.All.29 | [INF] Production.Edit.Digitized: Not mapped to an aiWare schema | clip: clipData[212]<AiWare.Report.All.29>; byIds: list[0].clipData[212]<AiWare.Report.All.29> |
| id | 2843621790 | clip: clipData[212].id; byIds: list[0].clipData[212].id |
| AiWare.Report.All.26 | [INF] Production.DEFA: Not mapped to an aiWare schema | clip: clipData[213]<AiWare.Report.All.26>; byIds: list[0].clipData[213]<AiWare.Report.All.26> |
| id | 2843621791 | clip: clipData[213].id; byIds: list[0].clipData[213].id |
| AiWare.Report.All.27 | [INF] Production.Edit.Cleanfeed: Not mapped to an aiWare schema | clip: clipData[214]<AiWare.Report.All.27>; byIds: list[0].clipData[214]<AiWare.Report.All.27> |
| id | 2843621792 | clip: clipData[214].id; byIds: list[0].clipData[214].id |
| AiWare.Report.All.24 | [INF] Production.CountryOfOrigin.EN: Not mapped to an aiWare schema | clip: clipData[215]<AiWare.Report.All.24>; byIds: list[0].clipData[215]<AiWare.Report.All.24> |
| id | 2843621793 | clip: clipData[215].id; byIds: list[0].clipData[215].id |
| AiWare.Report.All.68 | [INF] Title.DE: Not mapped to an aiWare schema | clip: clipData[216]<AiWare.Report.All.68>; byIds: list[0].clipData[216]<AiWare.Report.All.68> |
| id | 2843621794 | clip: clipData[216].id; byIds: list[0].clipData[216].id |
| AiWare.Report.All.25 | [INF] Production.CountryOfOrigin.FR: Not mapped to an aiWare schema | clip: clipData[217]<AiWare.Report.All.25>; byIds: list[0].clipData[217]<AiWare.Report.All.25> |
| id | 2843621795 | clip: clipData[217].id; byIds: list[0].clipData[217].id |
| AiWare.Report.All.69 | [INF] Title.EN: Not mapped to an aiWare schema | clip: clipData[218]<AiWare.Report.All.69>; byIds: list[0].clipData[218]<AiWare.Report.All.69> |
| id | 2843621796 | clip: clipData[218].id; byIds: list[0].clipData[218].id |
| AiWare.Report.All.33 | [INF] Production.FrameRate: Not mapped to an aiWare schema | clip: clipData[219]<AiWare.Report.All.33>; byIds: list[0].clipData[219]<AiWare.Report.All.33> |
| id | 2843621797 | clip: clipData[219].id; byIds: list[0].clipData[219].id |
| AiWare.Report.All.77 | [INF] https://s3-t3m-previewpriv-or-1.s3.us-west-2.amazonaws.com/1RV/F3C/1RVF3C_JBCE3SSZRS_mp.f4v: Asset created | clip: clipData[220]<AiWare.Report.All.77>; byIds: list[0].clipData[220]<AiWare.Report.All.77> |
| id | 2843621798 | clip: clipData[220].id; byIds: list[0].clipData[220].id |
| AiWare.Report.All.34 | [INF] Production.Genre.DE: Not mapped to an aiWare schema | clip: clipData[221]<AiWare.Report.All.34>; byIds: list[0].clipData[221]<AiWare.Report.All.34> |
| id | 2843621799 | clip: clipData[221].id; byIds: list[0].clipData[221].id |
| AiWare.Report.All.78 | [INF] https://s3-t3m-previewpriv-or-1.s3.us-west-2.amazonaws.com/1RV/F3C/1RVF3C_JBCE3SSZRS_xp.f4v: Asset created | clip: clipData[222]<AiWare.Report.All.78>; byIds: list[0].clipData[222]<AiWare.Report.All.78> |
| id | 2843621800 | clip: clipData[222].id; byIds: list[0].clipData[222].id |
| AiWare.Report.All.31 | [INF] Production.Format.Digitized: Not mapped to an aiWare schema | clip: clipData[223]<AiWare.Report.All.31>; byIds: list[0].clipData[223]<AiWare.Report.All.31> |
| id | 2843621801 | clip: clipData[223].id; byIds: list[0].clipData[223].id |
| AiWare.Report.All.75 | [INF] https://s3-t3m-previewpriv-or-1.s3.us-west-2.amazonaws.com/1RV/F3C/1RVF3C_JBCE3SSZRS_lp-wmpg%2Covtc.f4v: Asset cr… | clip: clipData[224]<AiWare.Report.All.75>; byIds: list[0].clipData[224]<AiWare.Report.All.75> |
| id | 2843621802 | clip: clipData[224].id; byIds: list[0].clipData[224].id |
| AiWare.Report.All.32 | [INF] Production.Format.Original: Not mapped to an aiWare schema | clip: clipData[225]<AiWare.Report.All.32>; byIds: list[0].clipData[225]<AiWare.Report.All.32> |
| id | 2843621803 | clip: clipData[225].id; byIds: list[0].clipData[225].id |
| AiWare.Report.All.76 | [INF] https://cdnt3m-a.akamaihd.net/tem/warehouse/1RV/F3C/1RVF3C_JBCE3SSZRS_lt.jpg: Asset created | clip: clipData[226]<AiWare.Report.All.76>; byIds: list[0].clipData[226]<AiWare.Report.All.76> |
| id | 2843621804 | clip: clipData[226].id; byIds: list[0].clipData[226].id |
| AiWare.Report.All.73 | [INF] Transcription.EN: Not mapped to an aiWare schema | clip: clipData[227]<AiWare.Report.All.73>; byIds: list[0].clipData[227]<AiWare.Report.All.73> |
| id | 2843621805 | clip: clipData[227].id; byIds: list[0].clipData[227].id |
| AiWare.Report.All.30 | [INF] Production.Format: Not mapped to an aiWare schema | clip: clipData[228]<AiWare.Report.All.30>; byIds: list[0].clipData[228]<AiWare.Report.All.30> |
| id | 2843621806 | clip: clipData[228].id; byIds: list[0].clipData[228].id |
| AiWare.Report.All.74 | [INF] Workflow.Transcript.Status: Not mapped to an aiWare schema | clip: clipData[229]<AiWare.Report.All.74>; byIds: list[0].clipData[229]<AiWare.Report.All.74> |
| id | 2843621807 | clip: clipData[229].id; byIds: list[0].clipData[229].id |
| AiWare.Report.All.71 | [INF] Topic.Discovery: Not mapped to an aiWare schema | clip: clipData[230]<AiWare.Report.All.71>; byIds: list[0].clipData[230]<AiWare.Report.All.71> |
| id | 2843621808 | clip: clipData[230].id; byIds: list[0].clipData[230].id |
| AiWare.Report.All.72 | [INF] Transcription.Corrected: Not mapped to an aiWare schema | clip: clipData[231]<AiWare.Report.All.72>; byIds: list[0].clipData[231]<AiWare.Report.All.72> |
| id | 2843621809 | clip: clipData[231].id; byIds: list[0].clipData[231].id |
| AiWare.Report.All.70 | [INF] Title.FR: Not mapped to an aiWare schema | clip: clipData[232]<AiWare.Report.All.70>; byIds: list[0].clipData[232]<AiWare.Report.All.70> |
| id | 2843621810 | clip: clipData[232].id; byIds: list[0].clipData[232].id |
| AiWare.Report.All.19 | [INF] Production.Codec: Not mapped to an aiWare schema | clip: clipData[233]<AiWare.Report.All.19>; byIds: list[0].clipData[233]<AiWare.Report.All.19> |
| id | 2843621811 | clip: clipData[233].id; byIds: list[0].clipData[233].id |
| AiWare.Report.All.17 | [INF] Production.AudioSampleRate: Not mapped to an aiWare schema | clip: clipData[234]<AiWare.Report.All.17>; byIds: list[0].clipData[234]<AiWare.Report.All.17> |
| id | 2843621812 | clip: clipData[234].id; byIds: list[0].clipData[234].id |
| AiWare.Report.All.18 | [INF] Production.ClosedCaption: Not mapped to an aiWare schema | clip: clipData[235]<AiWare.Report.All.18>; byIds: list[0].clipData[235]<AiWare.Report.All.18> |
| id | 2843621813 | clip: clipData[235].id; byIds: list[0].clipData[235].id |
| AiWare.Report.All.15 | [INF] Production.AspectRatio: Not mapped to an aiWare schema | clip: clipData[236]<AiWare.Report.All.15>; byIds: list[0].clipData[236]<AiWare.Report.All.15> |
| id | 2843621814 | clip: clipData[236].id; byIds: list[0].clipData[236].id |
| AiWare.Report.All.59 | [INF] Production.User.Id: Not mapped to an aiWare schema | clip: clipData[237]<AiWare.Report.All.59>; byIds: list[0].clipData[237]<AiWare.Report.All.59> |
| id | 2843621815 | clip: clipData[237].id; byIds: list[0].clipData[237].id |
| AiWare.Report.All.16 | [INF] Production.AudioBitDepth: Not mapped to an aiWare schema | clip: clipData[238]<AiWare.Report.All.16>; byIds: list[0].clipData[238]<AiWare.Report.All.16> |
| id | 2843621816 | clip: clipData[238].id; byIds: list[0].clipData[238].id |
| AiWare.Report.All.13 | [INF] Production.Accounting.ArticleRange: Not mapped to an aiWare schema | clip: clipData[239]<AiWare.Report.All.13>; byIds: list[0].clipData[239]<AiWare.Report.All.13> |
| id | 2843621817 | clip: clipData[239].id; byIds: list[0].clipData[239].id |
| AiWare.Report.All.57 | [INF] Production.Talent.Cast.Principals.EN: Not mapped to an aiWare schema | clip: clipData[240]<AiWare.Report.All.57>; byIds: list[0].clipData[240]<AiWare.Report.All.57> |
| id | 2843621818 | clip: clipData[240].id; byIds: list[0].clipData[240].id |
| AiWare.Report.All.14 | [INF] Production.Accounting.License: Not mapped to an aiWare schema | clip: clipData[241]<AiWare.Report.All.14>; byIds: list[0].clipData[241]<AiWare.Report.All.14> |
| id | 2843621819 | clip: clipData[241].id; byIds: list[0].clipData[241].id |
| AiWare.Report.All.58 | [INF] Production.Talent.Cast.Principals.FR: Not mapped to an aiWare schema | clip: clipData[242]<AiWare.Report.All.58>; byIds: list[0].clipData[242]<AiWare.Report.All.58> |
| id | 2843621820 | clip: clipData[242].id; byIds: list[0].clipData[242].id |
| AiWare.Report.All.4 | [INF] Description.DE: Not mapped to an aiWare schema | clip: clipData[243]<AiWare.Report.All.4>; byIds: list[0].clipData[243]<AiWare.Report.All.4> |
| id | 2843621821 | clip: clipData[243].id; byIds: list[0].clipData[243].id |
| AiWare.Report.All.22 | [INF] Production.Cognition.TextRecognition: Not mapped to an aiWare schema | clip: clipData[244]<AiWare.Report.All.22>; byIds: list[0].clipData[244]<AiWare.Report.All.22> |
| id | 2843621822 | clip: clipData[244].id; byIds: list[0].clipData[244].id |
| AiWare.Report.All.66 | [INF] TE.Priority: Not mapped to an aiWare schema | clip: clipData[245]<AiWare.Report.All.66>; byIds: list[0].clipData[245]<AiWare.Report.All.66> |
| id | 2843621823 | clip: clipData[245].id; byIds: list[0].clipData[245].id |
| AiWare.Report.All.5 | [INF] Description.EN: Not mapped to an aiWare schema | clip: clipData[246]<AiWare.Report.All.5>; byIds: list[0].clipData[246]<AiWare.Report.All.5> |
| id | 2843621824 | clip: clipData[246].id; byIds: list[0].clipData[246].id |
| AiWare.Report.All.23 | [INF] Production.CountryOfOrigin.DE: Not mapped to an aiWare schema | clip: clipData[247]<AiWare.Report.All.23>; byIds: list[0].clipData[247]<AiWare.Report.All.23> |
| id | 2843621825 | clip: clipData[247].id; byIds: list[0].clipData[247].id |
| AiWare.Report.All.67 | [INF] TE.ZombieDate: Not mapped to an aiWare schema | clip: clipData[248]<AiWare.Report.All.67>; byIds: list[0].clipData[248]<AiWare.Report.All.67> |
| id | 2843621826 | clip: clipData[248].id; byIds: list[0].clipData[248].id |
| AiWare.Report.All.2 | [INF] Commerce.Rendition: Not mapped to an aiWare schema | clip: clipData[249]<AiWare.Report.All.2>; byIds: list[0].clipData[249]<AiWare.Report.All.2> |
| id | 2843621827 | clip: clipData[249].id; byIds: list[0].clipData[249].id |
| AiWare.Report.All.20 | [INF] Production.Cognition.FaceRecognition: Not mapped to an aiWare schema | clip: clipData[250]<AiWare.Report.All.20>; byIds: list[0].clipData[250]<AiWare.Report.All.20> |
| id | 2843621828 | clip: clipData[250].id; byIds: list[0].clipData[250].id |
| AiWare.Report.All.64 | [INF] TE.IsUpdate: Not mapped to an aiWare schema | clip: clipData[251]<AiWare.Report.All.64>; byIds: list[0].clipData[251]<AiWare.Report.All.64> |
| id | 2843621829 | clip: clipData[251].id; byIds: list[0].clipData[251].id |
| AiWare.Report.All.3 | [INF] DMH.Notes2: Not mapped to an aiWare schema | clip: clipData[252]<AiWare.Report.All.3>; byIds: list[0].clipData[252]<AiWare.Report.All.3> |
| id | 2843621830 | clip: clipData[252].id; byIds: list[0].clipData[252].id |
| AiWare.Report.All.21 | [INF] Production.Cognition.SpeakerSeperation: Not mapped to an aiWare schema | clip: clipData[253]<AiWare.Report.All.21>; byIds: list[0].clipData[253]<AiWare.Report.All.21> |
| id | 2843621831 | clip: clipData[253].id; byIds: list[0].clipData[253].id |
| AiWare.Report.All.65 | [INF] TE.LiveDate: Not mapped to an aiWare schema | clip: clipData[254]<AiWare.Report.All.65>; byIds: list[0].clipData[254]<AiWare.Report.All.65> |
| id | 2843621832 | clip: clipData[254].id; byIds: list[0].clipData[254].id |
| AiWare.Report.All.62 | [INF] Supplier.Title: Not mapped to an aiWare schema | clip: clipData[255]<AiWare.Report.All.62>; byIds: list[0].clipData[255]<AiWare.Report.All.62> |
| id | 2843621833 | clip: clipData[255].id; byIds: list[0].clipData[255].id |
| AiWare.Report.All.1 | [INF] Audio.Notes: Not mapped to an aiWare schema | clip: clipData[256]<AiWare.Report.All.1>; byIds: list[0].clipData[256]<AiWare.Report.All.1> |
| id | 2843621834 | clip: clipData[256].id; byIds: list[0].clipData[256].id |
| AiWare.Report.All.63 | [INF] Supplier.Uuid: Not mapped to an aiWare schema | clip: clipData[257]<AiWare.Report.All.63>; byIds: list[0].clipData[257]<AiWare.Report.All.63> |
| id | 2843621835 | clip: clipData[257].id; byIds: list[0].clipData[257].id |
| AiWare.Report.All.60 | [INF] Supplier.ParentClip: Not mapped to an aiWare schema | clip: clipData[258]<AiWare.Report.All.60>; byIds: list[0].clipData[258]<AiWare.Report.All.60> |
| id | 2843621836 | clip: clipData[258].id; byIds: list[0].clipData[258].id |
| AiWare.Report.All.61 | [INF] Supplier.Rights: Not mapped to an aiWare schema | clip: clipData[259]<AiWare.Report.All.61>; byIds: list[0].clipData[259]<AiWare.Report.All.61> |
| id | 2843621837 | clip: clipData[259].id; byIds: list[0].clipData[259].id |
| AiWare.Report.All.8 | [INF] Format.ScanType.Detail: Not mapped to an aiWare schema | clip: clipData[260]<AiWare.Report.All.8>; byIds: list[0].clipData[260]<AiWare.Report.All.8> |
| id | 2843621838 | clip: clipData[260].id; byIds: list[0].clipData[260].id |
| AiWare.Report.All.9 | [INF] Keywords.DE: Not mapped to an aiWare schema | clip: clipData[261]<AiWare.Report.All.9>; byIds: list[0].clipData[261]<AiWare.Report.All.9> |
| id | 2843621839 | clip: clipData[261].id; byIds: list[0].clipData[261].id |
| AiWare.Report.All.6 | [INF] Description.FR: Not mapped to an aiWare schema | clip: clipData[262]<AiWare.Report.All.6>; byIds: list[0].clipData[262]<AiWare.Report.All.6> |
| id | 2843621840 | clip: clipData[262].id; byIds: list[0].clipData[262].id |
| AiWare.Report.All.7 | [INF] Format.ScanType.ContainsInterlaced: Not mapped to an aiWare schema | clip: clipData[263]<AiWare.Report.All.7>; byIds: list[0].clipData[263]<AiWare.Report.All.7> |
| id | 2843621841 | clip: clipData[263].id; byIds: list[0].clipData[263].id |
| AiWare.TDO.Id | 3710569294 | clip: clipData[264]<AiWare.TDO.Id>; clipDetail: metaDataDefault[6]<AiWare.TDO.Id>; byIds: list[0].clipData[264]<AiWare.… |
| id | 2843621842 | clip: clipData[264].id; byIds: list[0].clipData[264].id |
| modified | 2025-07-16T11:30:59Z | clip: clipData[264].modified; byIds: list[0].clipData[264].modified |
| AiWare.Transcription.Timeline | [15;27-23;29] Der Jüdische Friedhof in Berlin Weißensee. 1880 wurde er geweiht. [24;11-30;05] 113.000 Menschen haben au… | clip: clipData[265]<AiWare.Transcription.Timeline>; clipDetail: detailTypeMap.secondary[0].timeline.data[0].section[0]<… |
| id | 2843621948 | clip: clipData[265].id; byIds: list[0].clipData[265].id |
| modified | 2025-07-16T11:35:19Z | clip: clipData[265].modified; byIds: list[0].clipData[265].modified |
| Rights.EditorialUse | none | clip: clipData[266]<Rights.EditorialUse>; byIds: list[0].clipData[266]<Rights.EditorialUse> |
| id | 3758538157 | clip: clipData[266].id; byIds: list[0].clipData[266].id |
| Rights.Geography | AD,AE,AF,AG,AI,AL,AM,AO,AQ,AR,AS,AU,AW,AX,AZ,BA,BB,BD,BF,BG,BH,BI,BJ,BL,BM,BN,BO,BQ,BR,BS,BT,BV,BW,BY,BZ,CA,CC,CD,CF,CG… | clip: clipData[267]<Rights.Geography>; byIds: list[0].clipData[267]<Rights.Geography> |
| id | 3758538158 | clip: clipData[267].id; byIds: list[0].clipData[267].id |
| Rights.Control.Clips | none | clip: clipData[268]<Rights.Control.Clips>; byIds: list[0].clipData[268]<Rights.Control.Clips> |
| id | 3758538159 | clip: clipData[268].id; byIds: list[0].clipData[268].id |
| id | 131042592 | clip: renditions[0].id; byIds: list[0].renditions[0].id |
| created | 2025-07-15T12:56:18Z | clip: renditions[0].created; byIds: list[0].renditions[0].created |
| format | f4v | clip: renditions[0].format; clip: renditions[4].format; clip: renditions[5].format (+9) |
| name | 1RV985_001_lp.f4v | clip: renditions[0].name; byIds: list[0].renditions[0].name |
| purpose | p | clip: renditions[0].purpose; clip: renditions[4].purpose; clip: renditions[5].purpose (+9) |
| size | s | clip: renditions[0].size; clip: renditions[2].size; clip: renditions[4].size (+3) |
| uri | t3://S3ViaAkamaiStream:2e6960df-8601-4595-b0cc-aaf7330c2e8a@s3-t3m-previewpriv-or-1.s3.amazonaws.com/1RV/985/1RV985_001… | clip: renditions[0].uri; byIds: list[0].renditions[0].uri |
| variant | ,wmpg, | clip: renditions[0].variant; clip: renditions[4].variant; byIds: list[0].renditions[0].variant (+1) |
| id | 131042593 | clip: renditions[1].id; byIds: list[0].renditions[1].id |
| created | 2025-07-15T12:56:19Z | clip: renditions[1].created; byIds: list[0].renditions[1].created |
| filesize | 110932480 | clip: renditions[1].filesize; byIds: list[0].renditions[1].filesize |
| format | mp4 | clip: renditions[1].format; clip: renditions[9].format; byIds: list[0].renditions[1].format (+1) |
| name | DEFA05341__Der Augenzeuge 1964-03.mp4 | clip: renditions[1].name; byIds: list[0].renditions[1].name |
| note | ,SourceReference=2025-07-15 12:55:12, | clip: renditions[1].note; byIds: list[0].renditions[1].note |
| purpose | m | clip: renditions[1].purpose; byIds: list[0].renditions[1].purpose |
| size | f | clip: renditions[1].size; byIds: list[0].renditions[1].size |
| uri | t3://S3ViaS3Signed:81b908cf-4aa4-4a4c-954d-70dbf3a69baa@s3-vtn-progress-editshare-or-1.s3.amazonaws.com/DEFA05341__Der+… | clip: renditions[1].uri; byIds: list[0].renditions[1].uri |
| id | 131042607 | clip: renditions[2].id; byIds: list[0].renditions[2].id |
| created | 2025-07-15T13:01:23Z | clip: renditions[2].created; byIds: list[0].renditions[2].created |
| filesize | 4401 | clip: renditions[2].filesize; byIds: list[0].renditions[2].filesize |
| format | jpg | clip: renditions[2].format; clip: renditions[3].format; clip: renditions[10].format (+3) |
| name | 1RVF3C_JBCE3SSZRS_st.jpg | clip: renditions[2].name; byIds: list[0].renditions[2].name |
| purpose | t | clip: renditions[2].purpose; clip: renditions[3].purpose; clip: renditions[10].purpose (+3) |
| uri | t3://S3ViaAkamai:f3427bd4-e75c-4e4d-9c16-7e4bb2ef8bf8@s3-t3m-previewpub-or-1.s3.amazonaws.com/1RV/F3C/1RVF3C_JBCE3SSZRS… | clip: renditions[2].uri; clip: renditions[3].uri; clip: renditions[10].uri (+3) |
| id | 131042608 | clip: renditions[3].id; byIds: list[0].renditions[3].id |
| created | 2025-07-15T13:01:24Z | clip: renditions[3].created; byIds: list[0].renditions[3].created |
| filesize | 41225 | clip: renditions[3].filesize; byIds: list[0].renditions[3].filesize |
| name | 1RVF3C_JBCE3SSZRS_lt.jpg | clip: renditions[3].name; byIds: list[0].renditions[3].name |
| size | l | clip: renditions[3].size; clip: renditions[5].size; clip: renditions[8].size (+3) |
| id | 131042609 | clip: renditions[4].id; byIds: list[0].renditions[4].id |
| created | 2025-07-15T13:01:25Z | clip: renditions[4].created; byIds: list[0].renditions[4].created |
| filesize | 1417582 | clip: renditions[4].filesize; byIds: list[0].renditions[4].filesize |
| name | 1RVF3C_JBCE3SSZRS_sp-wmpg.f4v | clip: renditions[4].name; byIds: list[0].renditions[4].name |
| uri | t3://S3ViaAkamaiStream:2e6960df-8601-4595-b0cc-aaf7330c2e8a@s3-t3m-previewpriv-or-1.s3.amazonaws.com/1RV/F3C/1RVF3C_JBC… | clip: renditions[4].uri; clip: renditions[5].uri; clip: renditions[6].uri (+7) |
| id | 131042630 | clip: renditions[5].id; byIds: list[0].renditions[5].id |
| created | 2025-07-15T13:04:44Z | clip: renditions[5].created; byIds: list[0].renditions[5].created |
| filesize | 50220715 | clip: renditions[5].filesize; byIds: list[0].renditions[5].filesize |
| name | 1RVF3C_JBCE3SSZRS_lp.f4v | clip: renditions[5].name; byIds: list[0].renditions[5].name |
| id | 131042633 | clip: renditions[6].id; byIds: list[0].renditions[6].id |
| created | 2025-07-15T13:05:48Z | clip: renditions[6].created; byIds: list[0].renditions[6].created |
| filesize | 50221561 | clip: renditions[6].filesize; byIds: list[0].renditions[6].filesize |
| name | 1RVF3C_JBCE3SSZRS_xp.f4v | clip: renditions[6].name; byIds: list[0].renditions[6].name |
| size | x | clip: renditions[6].size; clip: renditions[10].size; byIds: list[0].renditions[6].size (+1) |
| id | 131042637 | clip: renditions[7].id; byIds: list[0].renditions[7].id |
| created | 2025-07-15T13:05:56Z | clip: renditions[7].created; byIds: list[0].renditions[7].created |
| filesize | 2045621 | clip: renditions[7].filesize; byIds: list[0].renditions[7].filesize |
| name | 1RVF3C_JBCE3SSZRS_mp.f4v | clip: renditions[7].name; byIds: list[0].renditions[7].name |
| size | m | clip: renditions[7].size; clip: renditions[9].size; byIds: list[0].renditions[7].size (+1) |
| id | 131042638 | clip: renditions[8].id; byIds: list[0].renditions[8].id |
| created | 2025-07-15T13:06:02Z | clip: renditions[8].created; clip: renditions[9].created; byIds: list[0].renditions[8].created (+1) |
| filesize | 55505349 | clip: renditions[8].filesize; byIds: list[0].renditions[8].filesize |
| name | 1RVF3C_JBCE3SSZRS_lp-wmpg,ovtc.f4v | clip: renditions[8].name; byIds: list[0].renditions[8].name |
| variant | ,ovtc,wmpg, | clip: renditions[8].variant; clip: renditions[9].variant; byIds: list[0].renditions[8].variant (+1) |
| id | 131042639 | clip: renditions[9].id; byIds: list[0].renditions[9].id |
| filesize | 55646571 | clip: renditions[9].filesize; byIds: list[0].renditions[9].filesize |
| name | 1RVF3C_JBCE3SSZRS_mc-wmpg,ovtc.mp4 | clip: renditions[9].name; byIds: list[0].renditions[9].name |
| purpose | c | clip: renditions[9].purpose; byIds: list[0].renditions[9].purpose |
| uri | t3://S3ViaS3Signed:aab9d736-c46b-44f1-b7c6-99130bb8df9d@s3-t3m-compsfast-or-2.s3.amazonaws.com/1RV/F3C/1RVF3C_JBCE3SSZR… | clip: renditions[9].uri; byIds: list[0].renditions[9].uri |
| id | 131042677 | clip: renditions[10].id; byIds: list[0].renditions[10].id |
| created | 2025-07-15T13:14:05Z | clip: renditions[10].created; byIds: list[0].renditions[10].created |
| filesize | 403745 | clip: renditions[10].filesize; byIds: list[0].renditions[10].filesize |
| name | 1RVF3C_JBCE3SSZRS_xt.jpg | clip: renditions[10].name; byIds: list[0].renditions[10].name |
| priority | 5 | clip: priority; byIds: list[0].priority |
| supplierId | 31637981 | clip: supplierId; clip: supplier.data[0].supplierId; clip: supplier.data[1].supplierId (+43) |
| id | 31637981 | clip: supplier.id; byIds: list[0].supplier.id |
| address | – | clip: supplier.address; byIds: list[0].supplier.address |
| city | – | clip: supplier.city; byIds: list[0].supplier.city |
| contact | – | clip: supplier.contact; byIds: list[0].supplier.contact |
| country | – | clip: supplier.country; byIds: list[0].supplier.country |
| created | 2021-06-22T00:00:00Z | clip: supplier.created; byIds: list[0].supplier.created |
| description | – | clip: supplier.description; byIds: list[0].supplier.description |
| devName | progress | clip: supplier.devName; byIds: list[0].supplier.devName |
| email | – | clip: supplier.email; byIds: list[0].supplier.email |
| markup | – | clip: supplier.markup; byIds: list[0].supplier.markup |
| name | Progress | clip: supplier.name; byIds: list[0].supplier.name |
| phone | – | clip: supplier.phone; byIds: list[0].supplier.phone |
| rmPricing | false | clip: supplier.rmPricing; byIds: list[0].supplier.rmPricing |
| state | – | clip: supplier.state; byIds: list[0].supplier.state |
| supplierIds | 1RV | clip: supplier.supplierIds; byIds: list[0].supplier.supplierIds |
| type | Supplier | clip: supplier.type; byIds: list[0].supplier.type |
| zipcode | – | clip: supplier.zipcode; byIds: list[0].supplier.zipcode |
| UseStemmedThesaurus | true | clip: supplier.data[0]<UseStemmedThesaurus>; byIds: list[0].supplier.data[0]<UseStemmedThesaurus> |
| id | 45416 | clip: supplier.data[0].id; byIds: list[0].supplier.data[0].id |
| AiWare.ApiKey | 68b514:fac7b78087844aaf9b5cad552e4f43babd754db2a2ad4619b1f62fe75bd0269f | clip: supplier.data[1]<AiWare.ApiKey>; byIds: list[0].supplier.data[1]<AiWare.ApiKey> |
| id | 45417 | clip: supplier.data[1].id; byIds: list[0].supplier.data[1].id |
| AiWare.OrganizationId | 36170 | clip: supplier.data[2]<AiWare.OrganizationId>; byIds: list[0].supplier.data[2]<AiWare.OrganizationId> |
| id | 45418 | clip: supplier.data[2].id; byIds: list[0].supplier.data[2].id |
| AiWare.ImportAssets | false | clip: supplier.data[3]<AiWare.ImportAssets>; byIds: list[0].supplier.data[3]<AiWare.ImportAssets> |
| id | 45419 | clip: supplier.data[3].id; byIds: list[0].supplier.data[3].id |
| AiWare.AllowJobs | true | clip: supplier.data[4]<AiWare.AllowJobs>; byIds: list[0].supplier.data[4]<AiWare.AllowJobs> |
| id | 45420 | clip: supplier.data[4].id; byIds: list[0].supplier.data[4].id |
| Status | Active | clip: supplier.data[5]<Status>; byIds: list[0].supplier.data[5]<Status> |
| id | 45421 | clip: supplier.data[5].id; byIds: list[0].supplier.data[5].id |
| CategoryType | Platform | clip: supplier.data[6]<CategoryType>; byIds: list[0].supplier.data[6]<CategoryType> |
| id | 45422 | clip: supplier.data[6].id; byIds: list[0].supplier.data[6].id |
| Licensing | false | clip: supplier.data[7]<Licensing>; byIds: list[0].supplier.data[7]<Licensing> |
| id | 45423 | clip: supplier.data[7].id; byIds: list[0].supplier.data[7].id |
| Platform | true | clip: supplier.data[8]<Platform>; byIds: list[0].supplier.data[8]<Platform> |
| id | 45424 | clip: supplier.data[8].id; byIds: list[0].supplier.data[8].id |
| ContributorSegmentation | AllElse | clip: supplier.data[9]<ContributorSegmentation>; byIds: list[0].supplier.data[9]<ContributorSegmentation> |
| id | 45425 | clip: supplier.data[9].id; byIds: list[0].supplier.data[9].id |
| ContentCategory | Studio | clip: supplier.data[10]<ContentCategory>; byIds: list[0].supplier.data[10]<ContentCategory> |
| id | 45426 | clip: supplier.data[10].id; byIds: list[0].supplier.data[10].id |
| Exclusive | false | clip: supplier.data[11]<Exclusive>; byIds: list[0].supplier.data[11]<Exclusive> |
| id | 45427 | clip: supplier.data[11].id; byIds: list[0].supplier.data[11].id |
| AutoRenew | false | clip: supplier.data[12]<AutoRenew>; byIds: list[0].supplier.data[12]<AutoRenew> |
| id | 45428 | clip: supplier.data[12].id; byIds: list[0].supplier.data[12].id |
| Fee.Platform.Transcode | 0 | clip: supplier.data[13]<Fee.Platform.Transcode>; byIds: list[0].supplier.data[13]<Fee.Platform.Transcode> |
| id | 45886 | clip: supplier.data[13].id; byIds: list[0].supplier.data[13].id |
| Fee.Platform.International | 0 | clip: supplier.data[14]<Fee.Platform.International>; byIds: list[0].supplier.data[14]<Fee.Platform.International> |
| id | 45887 | clip: supplier.data[14].id; byIds: list[0].supplier.data[14].id |
| Fee.Platform.Offline | 0 | clip: supplier.data[15]<Fee.Platform.Offline>; byIds: list[0].supplier.data[15]<Fee.Platform.Offline> |
| id | 45888 | clip: supplier.data[15].id; byIds: list[0].supplier.data[15].id |
| Fee.Platform.Storage | 0 | clip: supplier.data[16]<Fee.Platform.Storage>; byIds: list[0].supplier.data[16]<Fee.Platform.Storage> |
| id | 45889 | clip: supplier.data[16].id; byIds: list[0].supplier.data[16].id |
| Supplier.Tier | 5 | clip: supplier.data[17]<Supplier.Tier>; byIds: list[0].supplier.data[17]<Supplier.Tier> |
| id | 45890 | clip: supplier.data[17].id; byIds: list[0].supplier.data[17].id |
| TemSearchSupplierRank | 5 | clip: supplier.data[18]<TemSearchSupplierRank>; byIds: list[0].supplier.data[18]<TemSearchSupplierRank> |
| id | 45891 | clip: supplier.data[18].id; byIds: list[0].supplier.data[18].id |
| CorbisSearchSupplierRank | 5 | clip: supplier.data[19]<CorbisSearchSupplierRank>; byIds: list[0].supplier.data[19]<CorbisSearchSupplierRank> |
| id | 45892 | clip: supplier.data[19].id; byIds: list[0].supplier.data[19].id |
| BBCSearchSupplierRank | 5 | clip: supplier.data[20]<BBCSearchSupplierRank>; byIds: list[0].supplier.data[20]<BBCSearchSupplierRank> |
| id | 45893 | clip: supplier.data[20].id; byIds: list[0].supplier.data[20].id |
| Media.Contact | alerts-uk-dmh-workflo-aaaae2sevzjiaulswcpa5rqhbu@veritone.slack.com | clip: supplier.data[21]<Media.Contact>; byIds: list[0].supplier.data[21]<Media.Contact> |
| id | 46227 | clip: supplier.data[21].id; byIds: list[0].supplier.data[21].id |
| zombieDate | 2025-07-15T13:14:48Z | clip: zombieDate; byIds: list[0].zombieDate |
| assetId | 60228265 | clipDetail: assetId |
| lastUpdated | 2025-01-21T11:40:48Z | clipDetail: detailTypeMap.lastUpdated |
| createdOn | 2022-06-24T04:29:55Z | clipDetail: detailTypeMap.createdOn |
| id | 299 | clipDetail: detailTypeMap.id |
| siteName | progress | clipDetail: detailTypeMap.siteName |
| name | Anonymous | clipDetail: detailTypeMap.name |
| filter | true | clipDetail: detailTypeMap.filter |
| name | content_details | clipDetail: detailTypeMap.secondary[0].content_details.name |
| name | Production.Original.AirDate | clipDetail: detailTypeMap.secondary[0].content_details.data[0].section[4].name |
| name | ContentNotes.DE | clipDetail: detailTypeMap.secondary[0].content_details.data[0].section[9].name |
| name | ContentNotes.EN | clipDetail: detailTypeMap.secondary[0].content_details.data[0].section[10].name |
| name | Production.CountryOfAction.DE | clipDetail: detailTypeMap.secondary[0].content_details.data[1].section[2].name |
| name | Production.CountryOfAction.EN | clipDetail: detailTypeMap.secondary[0].content_details.data[1].section[3].name |
| name | Production.RegionOfOrigin.DE | clipDetail: detailTypeMap.secondary[0].content_details.data[1].section[4].name |
| name | Production.RegionOfOrigin.EN | clipDetail: detailTypeMap.secondary[0].content_details.data[1].section[5].name |
| name | Production.CityOfOrigin.DE | clipDetail: detailTypeMap.secondary[0].content_details.data[1].section[6].name |
| name | Production.CityOfOrigin.EN | clipDetail: detailTypeMap.secondary[0].content_details.data[1].section[7].name |
| name | Keywords | clipDetail: detailTypeMap.secondary[0].content_details.data[2].section[2].name |
| name | Production.Shotlist | clipDetail: detailTypeMap.secondary[0].content_details.data[2].section[9].name |
| name | cast_crew | clipDetail: detailTypeMap.secondary[0].cast_crew.name |
| name | Production.Talent.Director.DE | clipDetail: detailTypeMap.secondary[0].cast_crew.data[0].section[0].name |
| name | Production.Talent.Director.EN | clipDetail: detailTypeMap.secondary[0].cast_crew.data[0].section[1].name |
| name | Production.Talent.Cameraman.DE | clipDetail: detailTypeMap.secondary[0].cast_crew.data[0].section[2].name |
| name | Production.Talent.Cameraman.EN | clipDetail: detailTypeMap.secondary[0].cast_crew.data[0].section[3].name |
| name | Production.Actor.DE | clipDetail: detailTypeMap.secondary[0].cast_crew.data[0].section[4].name |
| name | Production.Actor.EN | clipDetail: detailTypeMap.secondary[0].cast_crew.data[0].section[5].name |
| name | Production.Talent.Editor.DE | clipDetail: detailTypeMap.secondary[0].cast_crew.data[0].section[6].name |
| name | Production.Talent.Editor.EN | clipDetail: detailTypeMap.secondary[0].cast_crew.data[0].section[7].name |
| name | Production.Talent.Producer.DE | clipDetail: detailTypeMap.secondary[0].cast_crew.data[0].section[8].name |
| name | Production.Talent.Producer.EN | clipDetail: detailTypeMap.secondary[0].cast_crew.data[0].section[9].name |
| name | Production.Talent.Director.Photography.DE | clipDetail: detailTypeMap.secondary[0].cast_crew.data[0].section[10].name |
| name | Production.Talent.Director.Photography.EN | clipDetail: detailTypeMap.secondary[0].cast_crew.data[0].section[11].name |
| name | Production.Talent.Composer.DE | clipDetail: detailTypeMap.secondary[0].cast_crew.data[0].section[12].name |
| name | Production.Talent.Composer.EN | clipDetail: detailTypeMap.secondary[0].cast_crew.data[0].section[13].name |
| name | technical_details | clipDetail: detailTypeMap.secondary[0].technical_details.name |
| name | related_assets | clipDetail: detailTypeMap.secondary[0].related_assets.name |
| name | Related Assets | clipDetail: detailTypeMap.secondary[0].related_assets.relatedQuery[0].name |
| relatedQueryId | 91 | clipDetail: detailTypeMap.secondary[0].related_assets.relatedQuery[0].relatedQueryId |
| pageSize | 20 | clipDetail: detailTypeMap.secondary[0].related_assets.relatedQuery[0].pageSize; clipDetail: detailTypeMap.secondary[0].… |
| sortId | 912 | clipDetail: detailTypeMap.secondary[0].related_assets.relatedQuery[0].sortId; clipDetail: detailTypeMap.secondary[0].re… |
| name | More from the same Genre | clipDetail: detailTypeMap.secondary[0].related_assets.relatedQuery[1].name |
| relatedQueryId | 99 | clipDetail: detailTypeMap.secondary[0].related_assets.relatedQuery[1].relatedQueryId |
| name | timeline | clipDetail: detailTypeMap.secondary[0].timeline.name |
| name | Transcription.Timeline.FR | clipDetail: detailTypeMap.secondary[0].timeline.data[0].section[1].name |
| name | AiWare.ObjectRecognition.Timeline | clipDetail: detailTypeMap.secondary[0].timeline.data[0].section[2].name |
| ingested | 2025-07-15 12:56:16.0 | clipDetail: detailTypeMap.common[2]<ingested> |
| liveDate | 2025-07-15 12:56:17.0 | clipDetail: detailTypeMap.common[3]<liveDate> |
| modified | 2026-09-21 12:27:04.0 | clipDetail: detailTypeMap.common[4]<modified> |
| stored | clip30secPreview | clipDetail: detailTypeMap.renditionUseTypes.stored |
| dynamic | clip30secPreview | clipDetail: detailTypeMap.renditionUseTypes.dynamic |
| resourceClass | Footage | clipDetail: resourceClass |
| hasDownloadableComp | false | clipDetail: hasDownloadableComp |
| price | 1.0 | clipDetail: price |
| accessPath | ContentFilter | clipDetail: accessPath |
| clipIngested | 2025-07-15 12:56:16.0 | clipDetail: metaDataDefault[8]<clipIngested> |
| TE.ParentClip | – | clipDetail: metaDataDefault[9]<TE.ParentClip> |
| AiWare.Cloned.TDO.Ids | – | clipDetail: metaDataDefault[10]<AiWare.Cloned.TDO.Ids> |
| Format.Duration.Display | 00:10:39 | clipDetail: metaDataDefault[11]<Format.Duration.Display> |


## 3. Feldnamen – OK

### Werte des Clips
Werte aus collections.json und der Identifier, gesucht in allen Clip-Feldern:

| Gesucht | Wert | Fundstelle | Feld | Treffer | Clip-Wert |
|---|---|---|---|---|---|
| 101a Genre German | Wochenschau | clip: clipData[34]<Production.Genre.DE> | Production.Genre.DE | exakt | Wochenschau |
| 006 Source PROGRESS | DEFA | clip: clipData[60]<Rights.Agent> | Rights.Agent | exakt | DEFA |
| Identifier | DEFA05341 | clip: clipData[61]<Supplier.Barcode> | Supplier.Barcode | exakt | DEFA05341 |
| 006 Source PROGRESS | DEFA | clip: clipData[65]<Supplier.Source> | Supplier.Source | exakt | DEFA |
| Identifier | DEFA05341 | clip: clipData[68]<TE.OriginalName> | TE.OriginalName | enthalten | s3-vtn-progress-editshare-or-1.s3.amazonaws.com/DEFA05341__Der+Augenzeuge+1964-03.mp4 |
| Identifier | DEFA05341 | clip: clipData[94]<SI.Original.Names> | SI.Original.Names | enthalten | s3-vtn-progress-editshare-or-1.s3.amazonaws.com/DEFA05341__Der+Augenzeuge+1964-03.mp4 DEFA05341__Der+Augenzeuge+1964-03… |
| Identifier | DEFA05341 | clip: clipData[109]<SI.Supplier.Reference> | SI.Supplier.Reference | enthalten | s3-vtn-progress-editshare-or-1.s3.amazonaws.com/DEFA05341__Der+Augenzeuge+1964-03.mp4 DEFA05341__Der+Augenzeuge+1964-03… |
| Identifier | DEFA05341 | clip: clipData[122]<SI.Master.S3.Key> | SI.Master.S3.Key | enthalten | DEFA05341__Der Augenzeuge 1964-03.mp4 |
| Identifier | DEFA05341 | clip: clipData[124]<SI.Master.Filename> | SI.Master.Filename | enthalten | DEFA05341__Der Augenzeuge 1964-03.mp4 |
| Identifier | DEFA05341 | clip: clipData[206]<AiWare.Report.All.82> | AiWare.Report.All.82 | enthalten | [INF] https://s3-vtn-progress-editshare-or-1.s3.us-west-2.amazonaws.com/DEFA05341__Der%20Augenzeuge%201964-03.mp4: Asse… |
| Identifier | DEFA05341 | clip: renditions[1].name | name | enthalten | DEFA05341__Der Augenzeuge 1964-03.mp4 |
| Identifier | DEFA05341 | clip: renditions[1].uri | uri | enthalten | t3://S3ViaS3Signed:81b908cf-4aa4-4a4c-954d-70dbf3a69baa@s3-vtn-progress-editshare-or-1.s3.amazonaws.com/DEFA05341__Der+… |
| Identifier | DEFA05341 | clipDetail: detailTypeMap.primary[4]<Supplier.Barcode> | Supplier.Barcode | exakt | DEFA05341 |
| 006 Source PROGRESS | DEFA | clipDetail: detailTypeMap.primary[8]<Supplier.Source> | Supplier.Source | exakt | DEFA |
| 101a Genre German | Wochenschau | clipDetail: detailTypeMap.secondary[0].content_details.data[0].section[7]<Production.Genre.DE> | Production.Genre.DE | exakt | Wochenschau |
| 101a Genre German | Wochenschau | byIds: list[0].clipData[34]<Production.Genre.DE> | Production.Genre.DE | exakt | Wochenschau |
| 006 Source PROGRESS | DEFA | byIds: list[0].clipData[60]<Rights.Agent> | Rights.Agent | exakt | DEFA |
| Identifier | DEFA05341 | byIds: list[0].clipData[61]<Supplier.Barcode> | Supplier.Barcode | exakt | DEFA05341 |
| 006 Source PROGRESS | DEFA | byIds: list[0].clipData[65]<Supplier.Source> | Supplier.Source | exakt | DEFA |
| Identifier | DEFA05341 | byIds: list[0].clipData[68]<TE.OriginalName> | TE.OriginalName | enthalten | s3-vtn-progress-editshare-or-1.s3.amazonaws.com/DEFA05341__Der+Augenzeuge+1964-03.mp4 |
| Identifier | DEFA05341 | byIds: list[0].clipData[94]<SI.Original.Names> | SI.Original.Names | enthalten | s3-vtn-progress-editshare-or-1.s3.amazonaws.com/DEFA05341__Der+Augenzeuge+1964-03.mp4 DEFA05341__Der+Augenzeuge+1964-03… |
| Identifier | DEFA05341 | byIds: list[0].clipData[109]<SI.Supplier.Reference> | SI.Supplier.Reference | enthalten | s3-vtn-progress-editshare-or-1.s3.amazonaws.com/DEFA05341__Der+Augenzeuge+1964-03.mp4 DEFA05341__Der+Augenzeuge+1964-03… |
| Identifier | DEFA05341 | byIds: list[0].clipData[122]<SI.Master.S3.Key> | SI.Master.S3.Key | enthalten | DEFA05341__Der Augenzeuge 1964-03.mp4 |
| Identifier | DEFA05341 | byIds: list[0].clipData[124]<SI.Master.Filename> | SI.Master.Filename | enthalten | DEFA05341__Der Augenzeuge 1964-03.mp4 |
| Identifier | DEFA05341 | byIds: list[0].clipData[206]<AiWare.Report.All.82> | AiWare.Report.All.82 | enthalten | [INF] https://s3-vtn-progress-editshare-or-1.s3.us-west-2.amazonaws.com/DEFA05341__Der%20Augenzeuge%201964-03.mp4: Asse… |
| Identifier | DEFA05341 | byIds: list[0].renditions[1].name | name | enthalten | DEFA05341__Der Augenzeuge 1964-03.mp4 |
| Identifier | DEFA05341 | byIds: list[0].renditions[1].uri | uri | enthalten | t3://S3ViaS3Signed:81b908cf-4aa4-4a4c-954d-70dbf3a69baa@s3-vtn-progress-editshare-or-1.s3.amazonaws.com/DEFA05341__Der+… |

### Felddefinitionen

| Abfrage | HTTP | Fehler | Rohdaten |
|---|---|---|---|
| fieldFormats_all | 400 | No field names were provided | 007_fieldFormats_all.json |
| fieldDefinition_all | 204 | – | 008_fieldDefinition_all.json |
| fieldFormats_1 | 200 | – | 009_fieldFormats_1.json |
| fieldFormats_2 | 200 | – | 010_fieldFormats_2.json |
| fieldFormats_3 | 200 | – | 011_fieldFormats_3.json |
| fieldFormats_4 | 200 | – | 012_fieldFormats_4.json |
| fieldFormats_5 | 200 | – | 013_fieldFormats_5.json |
| fieldFormats_6 | 200 | – | 014_fieldFormats_6.json |
| fieldFormats_7 | 200 | – | 015_fieldFormats_7.json |
| fieldFormats_8 | 200 | – | 016_fieldFormats_8.json |
| fieldFormats_9 | 200 | – | 017_fieldFormats_9.json |

Anzeigenamen in den Felddefinitionen:

| Bezeichnung | interner Name | gefunden in | Eintrag |
|---|---|---|---|
| Description | Description | name | {"name": "Description", "dataType": "paragraph", "array": false} |

### Filterbaum
85 Knoten, davon 11 mit Unterknoten. Rohdaten: 018_filter_tree.json

| Gruppe | Eigenschaften | Unterknoten | erste Unterknoten |
|---|---|---|---|
| root | filterId=10257, field=allSearchable, type=Text, count=-1 | 15 | Clip ID, Search AI generated metadata, Digitised, Decade, Collection |
| root > Search AI generated metadata | filterId=10246, type=List, count=-1 | 2 | Search Transcript (Original language), Search Objects (English) |
| root > Digitised | filterId=10209, field=Production.Edit.Digitized, type=ExclusiveList, count=-1 | 2 | Yes, No |
| root > Decade | filterId=10210, type=ExclusiveList, count=-1 | 13 | 1900, 1910, 1920, 1930, 1940 |
| root > Collection | filterId=13920, type=ExclusiveList, count=-1 | 19 | Blickpunkt, Cintec, Colonia Dignidad, DEFA B-Roll, DEFA Interviews |
| root > Source | filterId=10251, field=Supplier.Source, type=ExclusiveList, count=-1 | 13 | Colonia Dignidad / Villa Baviera, DEFA, Doclights, Deutsche Welle, Historiathek |
| root > Genre | filterId=10255, field=Production.Genre, fieldValue=Genre, type=ExclusiveList, count=0 | 8 | Animation, B-Roll, Documentary, Education and Training, Interview |
| root > Content Type | filterId=10247, field=Production.Format, type=ExclusiveList, count=-1 | 3 | Video, Image, Audio |
| root > Colour | filterId=14801, field=Production.Edit.Color , type=ExclusiveList, count=-1 | 2 | Yes, No |
| root > Sound | filterId=14800, field=Audio.Notes, type=ExclusiveList, count=-1 | 2 | Yes, No |
| root > Language | filterId=11387, field=Production.Language.Original, type=ExclusiveList, count=-1 | 5 | English, French, German, Russian, Vietnamese |

Werte aus collections.json im Filterbaum (Suche zuerst in der Gruppe mit gleicher Bezeichnung):

| Bezeichnung | Wert | gesucht in | Knoten | Eigenschaften |
|---|---|---|---|---|
| 006 Source PROGRESS | Historiathek | ganzer Baum | root > Source > Historiathek | filterId=10197, field=Supplier.Source, fieldValue=Historiathek, type=Link, count=907 |
| 006 Source PROGRESS | Katholisches Filmwerk | ganzer Baum | root > Source > Katholisches Filmwerk | filterId=11396, field=Supplier.Source, fieldValue=Katholisches Filmwerk, type=Link, count=106 |
| 006 Source PROGRESS | LYNXarchive | ganzer Baum | root > Source > LYNXarchive | filterId=11926, field=Supplier.Source, fieldValue=LYNXarchive, type=Link, count=1691 |
| 006 Source PROGRESS | Doclights | ganzer Baum | root > Source > Doclights | filterId=10195, field=Supplier.Source, fieldValue=Doclights, type=Link, count=2008 |
| 006 Source PROGRESS | DEFA | ganzer Baum | root > Source > DEFA | filterId=10196, field=Supplier.Source, fieldValue=DEFA , type=Link, count=19762 |
| 007 Collection PROGRESS | East German Film Archives (DEFA) | ganzer Baum | root > Collection > East German Film Archives (DEFA) | filterId=14794, field=Supplier.Collection, fieldValue=East German Film Archives, type=Link, count=5910 |
| 007 Collection PROGRESS | DEFA B-Roll | ganzer Baum | root > Collection > DEFA B-Roll | filterId=14792, field=Supplier.Collection, fieldValue=DEFA B-Roll, type=Link, count=663 |
| 007 Collection PROGRESS | Cintec | ganzer Baum | root > Collection > Cintec | filterId=14790, field=Supplier.Collection, fieldValue=Cintec, type=Link, count=2040 |
| 007 Collection PROGRESS | Thomas Grimm History Archive | ganzer Baum | root > Collection > Thomas Grimm History Archive | filterId=11394, field=Supplier.Collection, fieldValue=Thomas Grimm History Archive, type=Link, count=1779 |
| 101a Genre German | Dokumentarfilm | ganzer Baum | nicht gefunden | – |
| 101a Genre German | Wochenschau | ganzer Baum | nicht gefunden | – |
| 101a Genre German | Animationsfilm | ganzer Baum | root > Genre > Animation | filterId=14796, field=Production.Genre.DE, fieldValue=Animationsfilm, type=Link, count=2054 |
| 101a Genre German | Spielfilm und Fiktion | ganzer Baum | nicht gefunden | – |
| 101a Genre German | B-Roll | ganzer Baum | root > Genre > B-Roll | filterId=14797, field=Production.Genre.EN, fieldValue=B-Roll, type=Link, count=4123 |

### Kandidaten je Config-Eintrag

| Config-Eintrag | Feld | Punkte | Belege |
|---|---|---|---|
| field_clip_id | Supplier.Barcode | 3 | Clip-Wert: clip: clipData[61]<Supplier.Barcode> (exakt) |
| field_clip_id | Description | 2 | Felddefinition: Description in name |
| field_clip_id | TE.OriginalName | 1 | Clip-Wert: clip: clipData[68]<TE.OriginalName> (enthalten) |
| field_clip_id | SI.Original.Names | 1 | Clip-Wert: clip: clipData[94]<SI.Original.Names> (enthalten) |
| field_clip_id | SI.Supplier.Reference | 1 | Clip-Wert: clip: clipData[109]<SI.Supplier.Reference> (enthalten) |
| field_source | Supplier.Source | 5 | Clip-Wert: clip: clipData[65]<Supplier.Source> (exakt); Filterbaum-Wert: root > Source > Historiathek |
| field_source | Rights.Agent | 2 | Clip-Wert: clip: clipData[60]<Rights.Agent> (exakt) |
| field_collection | Supplier.Collection | 3 | Filterbaum-Wert: root > Collection > East German Film Archives (DEFA) |
| field_genre | Production.Genre.DE | 5 | Clip-Wert: clip: clipData[34]<Production.Genre.DE> (exakt); Filterbaum-Wert: root > Genre > Animation |
| field_genre | Production.Genre.EN | 3 | Filterbaum-Wert: root > Genre > B-Roll |

Felddefinition der besten Kandidaten:

| Config-Eintrag | Feld | HTTP | Antwort | Rohdaten |
|---|---|---|---|---|
| field_clip_id | Supplier.Barcode | 200 | {"name": "Supplier.Barcode", "interfaceRequired": false, "hideWhenEmpty": false, "dataType": "text", "inheritable": fal… | 019_fieldDefinition_Supplier_Barcode.json |
| field_clip_id | Description | 200 | {"name": "Description", "interfaceRequired": false, "hideWhenEmpty": false, "dataType": "paragraph", "inheritable": fal… | 020_fieldDefinition_Description.json |
| field_clip_id | TE.OriginalName | 200 | {"name": "TE.OriginalName", "interfaceRequired": false, "hideWhenEmpty": false, "dataType": "text", "inheritable": fals… | 021_fieldDefinition_TE_OriginalName.json |
| field_source | Supplier.Source | 200 | {"name": "Supplier.Source", "interfaceRequired": false, "hideWhenEmpty": false, "dataType": "text", "inheritable": fals… | 022_fieldDefinition_Supplier_Source.json |
| field_source | Rights.Agent | 200 | {"name": "Rights.Agent", "interfaceRequired": false, "hideWhenEmpty": false, "dataType": "paragraph", "inheritable": fa… | 023_fieldDefinition_Rights_Agent.json |
| field_collection | Supplier.Collection | 200 | {"name": "Supplier.Collection", "interfaceRequired": false, "hideWhenEmpty": false, "dataType": "text", "inheritable": … | 024_fieldDefinition_Supplier_Collection.json |
| field_genre | Production.Genre.DE | 200 | {"name": "Production.Genre.DE", "interfaceRequired": false, "hideWhenEmpty": false, "dataType": "text", "inheritable": … | 025_fieldDefinition_Production_Genre_DE.json |
| field_genre | Production.Genre.EN | 200 | {"name": "Production.Genre.EN", "interfaceRequired": false, "hideWhenEmpty": false, "dataType": "text", "inheritable": … | 026_fieldDefinition_Production_Genre_EN.json |


## 4. Gegenprobe mit dem Clip – FEHLER

advancedSearch je Kandidat (Is und Contains). Nach bestätigtem Identifier-Feld wird zusätzlich auf den Identifier eingeschränkt:

| Config-Eintrag | Feld | op | Wert | Zusatz | HTTP | totalCount | Ergebnis | Rohdaten |
|---|---|---|---|---|---|---|---|---|
| field_clip_id | Supplier.Barcode | Is | DEFA05341 | – | 400 | – | Invalid site name | 027_verify_field_clip_id_Supplier_Barcode_Is.json |
| field_clip_id | Supplier.Barcode | Contains | DEFA05341 | – | 400 | – | Invalid site name | 028_verify_field_clip_id_Supplier_Barcode_Contains.json |
| field_clip_id | Description | Is | DEFA05341 | – | 400 | – | Invalid site name | 029_verify_field_clip_id_Description_Is.json |
| field_clip_id | Description | Contains | DEFA05341 | – | 400 | – | Invalid site name | 030_verify_field_clip_id_Description_Contains.json |
| field_clip_id | TE.OriginalName | Is | DEFA05341 | – | 400 | – | Invalid site name | 031_verify_field_clip_id_TE_OriginalName_Is.json |
| field_clip_id | TE.OriginalName | Contains | DEFA05341 | – | 400 | – | Invalid site name | 032_verify_field_clip_id_TE_OriginalName_Contains.json |
| field_source | Supplier.Source | Is | DEFA | – | 400 | – | Invalid site name | 033_verify_field_source_Supplier_Source_Is.json |
| field_source | Supplier.Source | Contains | DEFA | – | 400 | – | Invalid site name | 034_verify_field_source_Supplier_Source_Contains.json |
| field_source | Rights.Agent | Is | DEFA | – | 400 | – | Invalid site name | 035_verify_field_source_Rights_Agent_Is.json |
| field_source | Rights.Agent | Contains | DEFA | – | 400 | – | Invalid site name | 036_verify_field_source_Rights_Agent_Contains.json |
| field_source | 006 Source PROGRESS | Is | DEFA | – | 400 | – | Invalid site name | 037_verify_field_source_006_Source_PROGRESS_Is.json |
| field_source | 006 Source PROGRESS | Contains | DEFA | – | 400 | – | Invalid site name | 038_verify_field_source_006_Source_PROGRESS_Contains.json |
| field_collection | Supplier.Collection | Is | East German Film Archives (DEFA) | – | 400 | – | Invalid site name | 039_verify_field_collection_Supplier_Collection_Is.json |
| field_collection | Supplier.Collection | Contains | East German Film Archives (DEFA) | – | 400 | – | Invalid site name | 040_verify_field_collection_Supplier_Collection_Contains.json |
| field_collection | Supplier.Collection | Is | East German Film Archives | – | 400 | – | Invalid site name | 041_verify_field_collection_Supplier_Collection_Is.json |
| field_collection | Supplier.Collection | Contains | East German Film Archives | – | 400 | – | Invalid site name | 042_verify_field_collection_Supplier_Collection_Contains.json |
| field_collection | 007 Collection PROGRESS | Is | East German Film Archives (DEFA) | – | 400 | – | Invalid site name | 043_verify_field_collection_007_Collection_PROGRESS_Is.json |
| field_collection | 007 Collection PROGRESS | Contains | East German Film Archives (DEFA) | – | 400 | – | Invalid site name | 044_verify_field_collection_007_Collection_PROGRESS_Contains.json |
| field_genre | Production.Genre.DE | Is | Wochenschau | – | 400 | – | Invalid site name | 045_verify_field_genre_Production_Genre_DE_Is.json |
| field_genre | Production.Genre.DE | Contains | Wochenschau | – | 400 | – | Invalid site name | 046_verify_field_genre_Production_Genre_DE_Contains.json |
| field_genre | Production.Genre.EN | Is | B-Roll | – | 400 | – | Invalid site name | 047_verify_field_genre_Production_Genre_EN_Is.json |
| field_genre | Production.Genre.EN | Contains | B-Roll | – | 400 | – | Invalid site name | 048_verify_field_genre_Production_Genre_EN_Contains.json |
| field_genre | 101a Genre German | Is | Wochenschau | – | 400 | – | Invalid site name | 049_verify_field_genre_101a_Genre_German_Is.json |
| field_genre | 101a Genre German | Contains | Wochenschau | – | 400 | – | Invalid site name | 050_verify_field_genre_101a_Genre_German_Contains.json |

Freitextsuche q=DEFA05341: HTTP 200, totalCount=1, Clip gefunden (051_search_identifier.json)

**Aufbau eines Suchtreffers** (Referenz-Clip aus Freitextsuche, Seitenfelder: totalCount, currentPage, pageSize, hasNextPage, numberOfPages, hasPreviousPage)

| Pfad | Feld | Wert |
|---|---|---|
| assetId | assetId | 60228265 |
| name | name | 1RVF3C_JBCE3SSZRS |
| metaData[0]<Title> | Title | Der Augenzeuge 1964/03 |
| metaData[1]<Description> | Description | 1. Millionen Juden klagen an\nDer "Augenzeuge" besuchte den größten Jüdischen Friedhof Deutschlands in Berlin-Weißensee… |
| metaData[2]<Description.Date> | Description.Date | 1964-01-01T00:00:00Z |
| metaData[3]<Supplier.Collection> | Supplier.Collection | East German Newsreel "Der Augenzeuge" |
| metaData[4]<Production.Genre.EN> | Production.Genre.EN | Newsreel |
| metaData[5]<Rights.Status> | Rights.Status | – |
| metaDataDefault[0]<TE.DigitalFormat> | TE.DigitalFormat | High Definition |
| metaDataDefault[1]<Resource.Class> | Resource.Class | Footage |
| metaDataDefault[2]<Format.TimeStart> | Format.TimeStart | 01:00:00:00 |
| metaDataDefault[3]<Format.FrameSize> | Format.FrameSize | 2048 x 1080 |
| metaDataDefault[4]<Format.FrameRate> | Format.FrameRate | 24 fps |
| metaDataDefault[5]<Format.Duration> | Format.Duration | 00:10:39 |
| metaDataDefault[6]<AiWare.TDO.Id> | AiWare.TDO.Id | 3710569294 |
| metaDataDefault[7]<Rights.Reproduction> | Rights.Reproduction | Rights Managed |
| metaDataDefault[8]<clipIngested> | clipIngested | 2025-07-15T12:56:16Z |
| metaDataDefault[9]<TE.ParentClip> | TE.ParentClip | – |
| metaDataDefault[10]<AiWare.Cloned.TDO.Ids> | AiWare.Cloned.TDO.Ids | – |
| metaDataDefault[11]<Format.Duration.Display> | Format.Duration.Display | – |
| thumbnail.name | name | thumbnail |
| thumbnail.urls.https | https | //cdnt3m-a.akamaihd.net/tem/warehouse/1RV/F3C/1RVF3C_JBCE3SSZRS_lt.jpg |
| hasDownloadableComp | hasDownloadableComp | false |


## 5. Kurzprüfung collections.json – UNKLAR

**Werte im Filterbaum**

| Bezeichnung | Wert | im Filterbaum | Knoten |
|---|---|---|---|
| 006 Source PROGRESS | Historiathek | ja | filterId=10197, field=Supplier.Source, fieldValue=Historiathek, type=Link, count=907 |
| 006 Source PROGRESS | Katholisches Filmwerk | ja | filterId=11396, field=Supplier.Source, fieldValue=Katholisches Filmwerk, type=Link, count=106 |
| 006 Source PROGRESS | LYNXarchive | ja | filterId=11926, field=Supplier.Source, fieldValue=LYNXarchive, type=Link, count=1691 |
| 006 Source PROGRESS | Doclights | ja | filterId=10195, field=Supplier.Source, fieldValue=Doclights, type=Link, count=2008 |
| 006 Source PROGRESS | DEFA | ja | filterId=10196, field=Supplier.Source, fieldValue=DEFA , type=Link, count=19762 |
| 007 Collection PROGRESS | East German Film Archives (DEFA) | ja | filterId=14794, field=Supplier.Collection, fieldValue=East German Film Archives, type=Link, count=5910 |
| 007 Collection PROGRESS | DEFA B-Roll | ja | filterId=14792, field=Supplier.Collection, fieldValue=DEFA B-Roll, type=Link, count=663 |
| 007 Collection PROGRESS | Cintec | ja | filterId=14790, field=Supplier.Collection, fieldValue=Cintec, type=Link, count=2040 |
| 007 Collection PROGRESS | Thomas Grimm History Archive | ja | filterId=11394, field=Supplier.Collection, fieldValue=Thomas Grimm History Archive, type=Link, count=1779 |
| 101a Genre German | Dokumentarfilm | nein | – |
| 101a Genre German | Wochenschau | nein | – |
| 101a Genre German | Animationsfilm | ja | filterId=14796, field=Production.Genre.DE, fieldValue=Animationsfilm, type=Link, count=2054 |
| 101a Genre German | Spielfilm und Fiktion | nein | – |
| 101a Genre German | B-Roll | ja | filterId=14797, field=Production.Genre.EN, fieldValue=B-Roll, type=Link, count=4123 |

**Abfrage je Kollektion** (alle Filter mit UND, pageSize 1, nur totalCount)

| Kollektion | HTTP | totalCount | Anzahl Filterbaum (bei 1 Filter) | Fehler | Rohdaten |
|---|---|---|---|---|---|
| Historiathek | – | – | – | Feld unklar: 006 Source PROGRESS | – |
| Katholisches Filmwerk | – | – | – | Feld unklar: 006 Source PROGRESS | – |
| LYNXarchive | – | – | – | Feld unklar: 006 Source PROGRESS | – |
| Doclights | – | – | – | Feld unklar: 006 Source PROGRESS | – |
| DEFA Dokumentation | – | – | – | Feld unklar: 006 Source PROGRESS, 007 Collection PROGRESS, 101a Genre German | – |
| DEFA Der Augenzeuge | – | – | – | Feld unklar: 006 Source PROGRESS, 101a Genre German | – |
| DEFA Animation | – | – | – | Feld unklar: 006 Source PROGRESS, 007 Collection PROGRESS, 101a Genre German | – |
| DEFA Spielfilme | – | – | – | Feld unklar: 006 Source PROGRESS, 007 Collection PROGRESS, 101a Genre German | – |
| DEFA Videoarchive B-Roll | – | – | – | Feld unklar: 006 Source PROGRESS, 007 Collection PROGRESS | – |
| DEFA Videoarchive Cintec | – | – | – | Feld unklar: 006 Source PROGRESS, 007 Collection PROGRESS, 101a Genre German | – |
| DEFA Videoarchive Thomas Grimm | – | – | – | Feld unklar: 006 Source PROGRESS, 007 Collection PROGRESS | – |


## 6. Vorschlag für Marathon – UNKLAR

~~~ini
# Anmeldung: query
[veritone]
# field_clip_id: nur Kandidat, ungeprüft
field_clip_id = Supplier.Barcode
# field_source: nur Kandidat, ungeprüft
field_source = Supplier.Source
# field_collection: nur Kandidat, ungeprüft
field_collection = Supplier.Collection
# field_genre: nur Kandidat, ungeprüft
field_genre = Production.Genre.DE
~~~


| Config-Eintrag | Bezeichnung | Feld | op | geprüfter Wert | Status |
|---|---|---|---|---|---|
| field_clip_id | Clip ID (Identifier DEFA05341) | Supplier.Barcode | – | – | nur Kandidat, ungeprüft |
| field_source | 006 Source PROGRESS | Supplier.Source | – | – | nur Kandidat, ungeprüft |
| field_collection | 007 Collection PROGRESS | Supplier.Collection | – | – | nur Kandidat, ungeprüft |
| field_genre | 101a Genre German | Production.Genre.DE | – | – | nur Kandidat, ungeprüft |

- Identifier im Suchtreffer unter: nicht ermittelt
- Clip-ID im Suchtreffer: assetId
- Blättern: nicht geprüft

## 7. Anhang: Aufrufe


| # | Methode | Pfad | Parameter | Anmeldung | HTTP | ms | Rohdaten |
|---|---|---|---|---|---|---|---|
| 1 | GET | /v1/search | {"q": "", "n": 1} | query | 200 | 901 | 001_auth_query.json |
| 2 | GET | /v1/search | {"q": "", "n": 1} | bearer | 200 | 799 | 002_auth_bearer.json |
| 3 | GET | /v1/clip/60228265 | {} | query | 200 | 1153 | 003_clip_clip.json |
| 4 | GET | /v1/clip/60228265/clipDetail | {} | query | 200 | 1090 | 004_clip_clipDetail.json |
| 5 | GET | /v1/clip/byIds | {"ids": 60228265} | query | 200 | 1194 | 005_clip_byIds.json |
| 6 | GET | /v1/assetInfo/view/clip/60228265/collection/0 | {} | query | 401 | 773 | 006_clip_assetInfo.json |
| 7 | GET | /v1/clip/fieldFormats | {} | query | 400 | 767 | 007_fieldFormats_all.json |
| 8 | GET | /v1/clip/fieldDefinition | {} | query | 204 | 760 | 008_fieldDefinition_all.json |
| 9 | GET | /v1/clip/fieldFormats | {"fieldNames": "id,family,ingested,liveDate,modified,name,SI.Resource.Modified,clipId,inherited,Resource.Family,Resourc… | query | 200 | 768 | 009_fieldFormats_1.json |
| 10 | GET | /v1/clip/fieldFormats | {"fieldNames": "Production.Format.Original,Production.FrameRate,Production.Genre.DE,Production.Genre.EN,Production.Genr… | query | 200 | 757 | 010_fieldFormats_2.json |
| 11 | GET | /v1/clip/fieldFormats | {"fieldNames": "Title.FR,Transcription.Corrected,Transcription.EN,Workflow.Transcript.Status,TE.DigitalFormat,TE.Priori… | query | 200 | 757 | 011_fieldFormats_3.json |
| 12 | GET | /v1/clip/fieldFormats | {"fieldNames": "SI.LicensableIn,SI.Channels.Public,SI.Channels.Protected,SI.Channels.Private,SI.Created.Timestamp,SI.Re… | query | 200 | 761 | 012_fieldFormats_4.json |
| 13 | GET | /v1/clip/fieldFormats | {"fieldNames": "Format.FieldOrder,Format.AudioSamplingRate,Format.FrameRateVariable,Format.TimecodeTrack.Present,Format… | query | 200 | 763 | 013_fieldFormats_5.json |
| 14 | GET | /v1/clip/fieldFormats | {"fieldNames": "AiWare.Report.All.39,AiWare.Report.All.37,AiWare.Report.All.38,AiWare.Report.All.35,AiWare.Report.All.7… | query | 200 | 755 | 014_fieldFormats_6.json |
| 15 | GET | /v1/clip/fieldFormats | {"fieldNames": "AiWare.Report.All.70,AiWare.Report.All.19,AiWare.Report.All.17,AiWare.Report.All.18,AiWare.Report.All.1… | query | 200 | 759 | 015_fieldFormats_7.json |
| 16 | GET | /v1/clip/fieldFormats | {"fieldNames": "size,uri,variant,filesize,note,priority,supplierId,address,city,contact,country,description,devName,ema… | query | 200 | 755 | 016_fieldFormats_8.json |
| 17 | GET | /v1/clip/fieldFormats | {"fieldNames": "CorbisSearchSupplierRank,BBCSearchSupplierRank,Media.Contact,zombieDate,assetId,lastUpdated,createdOn,s… | query | 200 | 755 | 017_fieldFormats_9.json |
| 18 | GET | /v1/filter/filterTree | {"counted": "true"} | query | 200 | 850 | 018_filter_tree.json |
| 19 | GET | /v1/clip/fieldDefinition | {"fieldName": "Supplier.Barcode"} | query | 200 | 755 | 019_fieldDefinition_Supplier_Barcode.json |
| 20 | GET | /v1/clip/fieldDefinition | {"fieldName": "Description"} | query | 200 | 756 | 020_fieldDefinition_Description.json |
| 21 | GET | /v1/clip/fieldDefinition | {"fieldName": "TE.OriginalName"} | query | 200 | 754 | 021_fieldDefinition_TE_OriginalName.json |
| 22 | GET | /v1/clip/fieldDefinition | {"fieldName": "Supplier.Source"} | query | 200 | 774 | 022_fieldDefinition_Supplier_Source.json |
| 23 | GET | /v1/clip/fieldDefinition | {"fieldName": "Rights.Agent"} | query | 200 | 767 | 023_fieldDefinition_Rights_Agent.json |
| 24 | GET | /v1/clip/fieldDefinition | {"fieldName": "Supplier.Collection"} | query | 200 | 766 | 024_fieldDefinition_Supplier_Collection.json |
| 25 | GET | /v1/clip/fieldDefinition | {"fieldName": "Production.Genre.DE"} | query | 200 | 766 | 025_fieldDefinition_Production_Genre_DE.json |
| 26 | GET | /v1/clip/fieldDefinition | {"fieldName": "Production.Genre.EN"} | query | 200 | 775 | 026_fieldDefinition_Production_Genre_EN.json |
| 27 | POST | /v1/search/advancedSearch | {"fieldExpression": {"fieldName": "Supplier.Barcode", "op": "Is", "value": "DEFA05341"}} | query | 400 | 858 | 027_verify_field_clip_id_Supplier_Barcode_Is.json |
| 28 | POST | /v1/search/advancedSearch | {"fieldExpression": {"fieldName": "Supplier.Barcode", "op": "Contains", "value": "DEFA05341"}} | query | 400 | 894 | 028_verify_field_clip_id_Supplier_Barcode_Contains.json |
| 29 | POST | /v1/search/advancedSearch | {"fieldExpression": {"fieldName": "Description", "op": "Is", "value": "DEFA05341"}} | query | 400 | 772 | 029_verify_field_clip_id_Description_Is.json |
| 30 | POST | /v1/search/advancedSearch | {"fieldExpression": {"fieldName": "Description", "op": "Contains", "value": "DEFA05341"}} | query | 400 | 892 | 030_verify_field_clip_id_Description_Contains.json |
| 31 | POST | /v1/search/advancedSearch | {"fieldExpression": {"fieldName": "TE.OriginalName", "op": "Is", "value": "DEFA05341"}} | query | 400 | 827 | 031_verify_field_clip_id_TE_OriginalName_Is.json |
| 32 | POST | /v1/search/advancedSearch | {"fieldExpression": {"fieldName": "TE.OriginalName", "op": "Contains", "value": "DEFA05341"}} | query | 400 | 1011 | 032_verify_field_clip_id_TE_OriginalName_Contains.json |
| 33 | POST | /v1/search/advancedSearch | {"fieldExpression": {"fieldName": "Supplier.Source", "op": "Is", "value": "DEFA"}} | query | 400 | 925 | 033_verify_field_source_Supplier_Source_Is.json |
| 34 | POST | /v1/search/advancedSearch | {"fieldExpression": {"fieldName": "Supplier.Source", "op": "Contains", "value": "DEFA"}} | query | 400 | 917 | 034_verify_field_source_Supplier_Source_Contains.json |
| 35 | POST | /v1/search/advancedSearch | {"fieldExpression": {"fieldName": "Rights.Agent", "op": "Is", "value": "DEFA"}} | query | 400 | 966 | 035_verify_field_source_Rights_Agent_Is.json |
| 36 | POST | /v1/search/advancedSearch | {"fieldExpression": {"fieldName": "Rights.Agent", "op": "Contains", "value": "DEFA"}} | query | 400 | 805 | 036_verify_field_source_Rights_Agent_Contains.json |
| 37 | POST | /v1/search/advancedSearch | {"fieldExpression": {"fieldName": "006 Source PROGRESS", "op": "Is", "value": "DEFA"}} | query | 400 | 813 | 037_verify_field_source_006_Source_PROGRESS_Is.json |
| 38 | POST | /v1/search/advancedSearch | {"fieldExpression": {"fieldName": "006 Source PROGRESS", "op": "Contains", "value": "DEFA"}} | query | 400 | 775 | 038_verify_field_source_006_Source_PROGRESS_Contains.json |
| 39 | POST | /v1/search/advancedSearch | {"fieldExpression": {"fieldName": "Supplier.Collection", "op": "Is", "value": "East German Film Archives (DEFA)"}} | query | 400 | 861 | 039_verify_field_collection_Supplier_Collection_Is.json |
| 40 | POST | /v1/search/advancedSearch | {"fieldExpression": {"fieldName": "Supplier.Collection", "op": "Contains", "value": "East German Film Archives (DEFA)"}} | query | 400 | 933 | 040_verify_field_collection_Supplier_Collection_Contains.json |
| 41 | POST | /v1/search/advancedSearch | {"fieldExpression": {"fieldName": "Supplier.Collection", "op": "Is", "value": "East German Film Archives"}} | query | 400 | 799 | 041_verify_field_collection_Supplier_Collection_Is.json |
| 42 | POST | /v1/search/advancedSearch | {"fieldExpression": {"fieldName": "Supplier.Collection", "op": "Contains", "value": "East German Film Archives"}} | query | 400 | 786 | 042_verify_field_collection_Supplier_Collection_Contains.json |
| 43 | POST | /v1/search/advancedSearch | {"fieldExpression": {"fieldName": "007 Collection PROGRESS", "op": "Is", "value": "East German Film Archives (DEFA)"}} | query | 400 | 779 | 043_verify_field_collection_007_Collection_PROGRESS_Is.json |
| 44 | POST | /v1/search/advancedSearch | {"fieldExpression": {"fieldName": "007 Collection PROGRESS", "op": "Contains", "value": "East German Film Archives (DEF… | query | 400 | 774 | 044_verify_field_collection_007_Collection_PROGRESS_Contains.json |
| 45 | POST | /v1/search/advancedSearch | {"fieldExpression": {"fieldName": "Production.Genre.DE", "op": "Is", "value": "Wochenschau"}} | query | 400 | 993 | 045_verify_field_genre_Production_Genre_DE_Is.json |
| 46 | POST | /v1/search/advancedSearch | {"fieldExpression": {"fieldName": "Production.Genre.DE", "op": "Contains", "value": "Wochenschau"}} | query | 400 | 979 | 046_verify_field_genre_Production_Genre_DE_Contains.json |
| 47 | POST | /v1/search/advancedSearch | {"fieldExpression": {"fieldName": "Production.Genre.EN", "op": "Is", "value": "B-Roll"}} | query | 400 | 901 | 047_verify_field_genre_Production_Genre_EN_Is.json |
| 48 | POST | /v1/search/advancedSearch | {"fieldExpression": {"fieldName": "Production.Genre.EN", "op": "Contains", "value": "B-Roll"}} | query | 400 | 783 | 048_verify_field_genre_Production_Genre_EN_Contains.json |
| 49 | POST | /v1/search/advancedSearch | {"fieldExpression": {"fieldName": "101a Genre German", "op": "Is", "value": "Wochenschau"}} | query | 400 | 777 | 049_verify_field_genre_101a_Genre_German_Is.json |
| 50 | POST | /v1/search/advancedSearch | {"fieldExpression": {"fieldName": "101a Genre German", "op": "Contains", "value": "Wochenschau"}} | query | 400 | 773 | 050_verify_field_genre_101a_Genre_German_Contains.json |
| 51 | GET | /v1/search | {"q": "DEFA05341", "n": 10, "i": 0} | query | 200 | 830 | 051_search_identifier.json |

