# Sample cargo data
cargo_data = [
    {'type': 'cargo', 'body': '1 Marmara => Odessa\n2-5000 mts mins in bb\nTtl days\n03-08 Dec\nDouble side holds only accepted\n3.75%\n+++', 'commission': 3.75, 'quantity': 5000},
    {'type': 'cargo', 'body': 'Poti => Odessa\n4000 - 5000 mt Urea in bb BB dimensions : 100cm x 100 cm x 100 cm (800 kg)\n2000/2000 sshexbe\nSPOT\n3.75%\n+++', 'commission': 3.75, 'quantity': 5000},
    {'type': 'cargo', 'body': 'Odessa => Alexandria\n7000 +/- 10% sunflower oil in bulk\n2000/2000 mts pwwd sshex eiu 02 - 09 DEC\n3.75%\n+++', 'commission': 3.75, 'quantity': 7000},
    {'type': 'cargo', 'body': 'Novorossiysk => Alexandria\nmin/max 10 000 mts steel billets 5k sshinc/3k fshex\n05-10 December\n3.75%\n+++', 'commission': 3.75, 'quantity': 10000},
    {'type': 'cargo', 'body': 'VARNA WEST => LAGOS, WC AFRICA\nTTL 12000 MTS SODA ASH IN BIG BAGS OF WHICH: - 9000 MT SODA ASH DENSE IN BIG BAGS STW ABT 1,3 CBM/MT UW 1,25 MT DIMS 1,2X1,2X1(H) M ADA - 3000 MT SODA ASH LIGHT IN BIG BAGS STW ABT 1,9 CBM/MT UW 1,25 MT DIMS 1,2X,1,2X1,6(H)M ADA (IN CHOPT 1000 MTS OF LIGHT SODA TO BE IN BIG BAGS OF UW 1MT DIMS 1,2X1,2X1,4(H) ADA)\n13/16 DEC\n13,5 TTL WWDS SSHEX EIU BE NEED BOX, GEARED TONNAGE PC OK\n5.0%\n+++', 'commission': 5.0, 'quantity': 12000},
    {'type': 'cargo', 'body': '1 CTZA-VARNA => 1 TUNISIE27/27.500 WHEAT\n5.000 SASHEX / 2.250 SASHEX PPT / ONW\nMax 20 years old is preferred max 190 LOA and max draft 32 feet disch\n2.5%\n+++', 'commission': 2.5, 'quantity': 27500},
    {'type': 'cargo', 'body': 'St. Petersburg => 1 Tunisia\n12000 mts 10% AN in blk (imo 5.1, un 1942)\n3000 sshinc / 1200 sshinc\n05-07 December\n5.0%\n+++', 'commission': 5.0, 'quantity': 12000},
    {'type': 'cargo', 'body': '1-2 KARASU-BANDIRMA-ISKENDERUN => 1 TUNISIE 25/27.500 WHEAT\n5.000 SASHEX / 2.250 SASHEX\n7 DEC / ONW\nMax 20 years old is preferred max 190 LOA and max draft 32 feet disch\n2.5%\n+++', 'commission': 2.5, 'quantity': 27500},
    {'type': 'cargo', 'body': 'KAVKAZ => 1 TUNISIE 27.500 WHEAT\n6.000 SASHEX / 2.250 SASHEX 15 DEC / ONW\nMax 20 years old is preferred max 190 LOA and max draft 32 feet disch\n2.5%\n+++', 'commission': 2.5, 'quantity': 27500},
    {'type': 'cargo', 'body': 'Jebel Ali, PG => 1 Libya\n25000 mts sugar in bags\n4000/2000 FSHEX\nPrompt\nGRD vessel\n3.75%\n+++', 'commission': 3.75, 'quantity': 25000},
    {'type': 'cargo', 'body': 'Kavkaz road => Qingdao or Tianjin or Shanghai\n55 000 mts +/-10% yellow peas, 45-46’\nL/C 1-5 DEC 23\nL/D 6000/8000 sshex be\n2.5%', 'commission': 2.5, 'quantity': 55000},
    # Add more cargo-related objects
]

# Sample ship data
ship_data = [
    {'type': 'ship', 'body': 'M/V Ocean Voyager\nAvailable for Charter\n\nCargo Capacity: 30,000 MT +/- 10%\nLoading Port: Houston, USA\nDischarging Port: Rotterdam, Netherlands\nLaycan: December 5-10\n\nFreight Rate: $12/MT\nDemurrage: $5,000/day\nCommission: 3.5%', 'commission': 3.5, 'quantity': 30000},
    {'type': 'ship', 'body': 'MV Sea Explorer\nOpen for Fixture\n\nCargo: 20,000 MT of Iron Ore in Bulk\nLoading: Brazil\nDischarging: Qingdao, China\nLaycan: December 8-15\n\nFreight Rate: $18/MT\nDemurrage: $6,000/day\nCommission: 4.0%', 'commission': 4.0, 'quantity': 20000},
    {'type': 'ship', 'body': 'Vessel: MV Star Voyager\nPosition: Singapore Anchorage\n\nCargo Available: 25,000 MT of Coal\nLaycan: Prompt\n\nFreight Rate: $15/MT\nDemurrage: $4,500/day\nCommission: 3.0%', 'commission': 3.0, 'quantity': 25000},
    {'type': 'ship', 'body': 'Vessel: MV Arctic Icebreaker\nAvailable for Fixture\n\nCargo: 38,000 MT of Coal\nLoading: St. Petersburg\nDischarging: Tunisia\nLaycan: December 5-10\n\nFreight Rate: $24/MT\nDemurrage: $8,000/day\nCommission: 4.75%', 'commission': 4.75, 'quantity': 38000},

    {'type': 'ship', 'body': 'Charter Opportunity - MV Blue Marlin\n\nCargo: 40,000 MT of Wheat in Bulk\nLoading: Black Sea\nDischarging: Alexandria, Egypt\nLaycan: December 12-20\n\nFreight Rate: $22/MT\nDemurrage: $7,000/day\nCommission: 3.75%', 'commission': 3.75, 'quantity': 40000},
    {'type': 'ship', 'body': 'MV Swift Wind\nOpen for Charter\n\nCargo Capacity: 35,000 MT of Corn in Bulk\nLoading: Argentina\nDischarging: China\nLaycan: December 5-12\n\nFreight Rate: $20/MT\nDemurrage: $6,500/day\nCommission: 4.5%', 'commission': 4.5, 'quantity': 35000},
    # Add more ship-related objects
    {'type': 'ship', 'body': 'Vessel: MV Arctic Icebreaker\nAvailable for Fixture\n\nCargo: 38,000 MT of Coal\nLoading: St. Petersburg\nDischarging: Tunisia\nLaycan: December 5-10\n\nFreight Rate: $24/MT\nDemurrage: $8,000/day\nCommission: 4.75%', 'commission': 4.75, 'quantity': 38000},

    {'type': 'ship', 'body': 'M/V Sunrise Explorer\nOpen for Fixture\n\nCargo: 28,000 MT of Soybeans\nLoading: Buenos Aires, Argentina\nDischarging: Qingdao, China\nLaycan: December 10-15\n\nFreight Rate: $16/MT\nDemurrage: $5,000/day\nCommission: 3.25%', 'commission': 3.25, 'quantity': 28000},
    {'type': 'ship', 'body': 'Vessel: MV Golden Gate\nAvailable for Charter\n\nCargo Capacity: 22,000 MT +/- 10%\nLoading Port: Paranagua, Brazil\nDischarging Port: Port Kelang, Malaysia\nLaycan: December 8-12\n\nFreight Rate: $14/MT\nDemurrage: $4,200/day\nCommission: 3.0%', 'commission': 3.0, 'quantity': 22000},
    {'type': 'ship', 'body': 'Charter Opportunity - MV Pacific Star\n\nCargo: 33,000 MT of Iron Ore Fines\nLoading: Walvis Bay, Namibia\nDischarging: Bilbao, Spain\nLaycan: December 15-20\n\nFreight Rate: $20/MT\nDemurrage: $6,800/day\nCommission: 4.0%', 'commission': 4.0, 'quantity': 33000},
    {'type': 'ship', 'body': 'MV Crystal Pearl\nOpen for Charter\n\nCargo Capacity: 25,000 MT of Rice in Bags\nLoading: Bangkok, Thailand\nDischarging: Lagos, Nigeria\nLaycan: December 12-18\n\nFreight Rate: $18/MT\nDemurrage: $5,500/day\nCommission: 3.5%', 'commission': 3.5, 'quantity': 25000},
    {'type': 'ship', 'body': 'Vessel: MV Arctic Icebreaker\nAvailable for Fixture\n\nCargo: 38,000 MT of Coal\nLoading: Newcastle, Australia\nDischarging: Chennai, India\nLaycan: December 5-10\n\nFreight Rate: $24/MT\nDemurrage: $8,000/day\nCommission: 4.75%', 'commission': 4.75, 'quantity': 38000},
    # Add more ship-related objects
]
