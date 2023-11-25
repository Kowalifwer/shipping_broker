x = """pls offer yr firm / rated cgo for mv A z a r a open Nemrut 01-02 dec

we hv interest for cgo ex odessa area

mvAZARA
IMO  9132492 Blt 1997
Palau Flag Shipping Register of Ukraine
DWT 13898 / Drft 8,214 mtr
BC,SID,grab disch,steel floored,
Grt/Nrt 10220/5123
LOA/Bm 142,14/22,2
4 HO / 4 HA,CO2 Fitted
Hatch open dims 1/2/3/4 15,75 x 14

        L      B      H      Grain/Bale

Hold 1  22,5   22,2   11,42  140804,90 / 137202,66
Hold 2  22,5   22,2   11,42  163901,55 / 156647,65
Hold 3  22,5   22,2   11,42  164537,24 / 156721,81
Hold 4  21,8   22,2   11,42  160546,54 / 156732,41

             total Grain/bale 629790,22 / 607304,53


Gears 4 crane,SWL 12.5 mts,positioned btwn holds - Considered as GearLess
PANDI: British Marine, Lux"""

real_response = {
    "entries": [
        {
            "type": "ship",
            "name": "MV AZARA",
            "status": "",
            "port": "Nemrut",
            "sea": "Mediterranean Sea",
            "month": "DEC",
            "capacity": "13898 DWT"
        },
        {
            "type": "cargo",
            "name": "",
            "quantity": "",
            "port_from": "Odessa area",
            "port_to": "",
            "sea_from": "",
            "sea_to": "",
            "month": "",
            "commission": ""
        }
    ]
}

expected_response = {
    "entries": [
        {
            "type": "ship",
            "name": "MV AZARA",
            "status": "open",
            "port": "Nemrut",
            "sea": "Aegean Sea",
            "month": "DEC",
            "capacity": "13898 DWT"
        }
    ]
}