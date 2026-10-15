from pathlib import Path
import sys

sys.path.insert(0,str(Path(__file__).resolve().parent / 'InflationItems/Codes/02_Alcohol_Tobacco/AlkolFiyatlariCo'))
import argparse

if __name__ == '__main__':
    parser=argparse.ArgumentParser(description='Alkol ve tutun kaynak gozlemleri')
    parser.add_argument('--source',choices=['whisky','birgun','raki','votka','bira','sarap','cin','tekila','likor'],default='whisky')
    args,remaining=parser.parse_known_args()
    if args.source in ('cin','tekila','likor'):
        from more_spirits_pilot import main
        raise SystemExit(main(args.source,remaining))
    elif args.source in ('bira','sarap'):
        from beer_wine_pilot import main
        raise SystemExit(main(args.source,remaining))
    elif args.source in ('raki','votka'):
        from spirits_pilot import main
        raise SystemExit(main(args.source,remaining))
    elif args.source=='birgun':
        from birgun_pilot import main
    else:
        from whisky_pilot import main
    raise SystemExit(main(remaining))
