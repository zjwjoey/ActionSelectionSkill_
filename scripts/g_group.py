"""Dot G-group entry: restore, verify, or original algorithm batch IO."""
import sys,argparse,json
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from runtime.g_handoff import restore,verify_restore,run
def main():
 p=argparse.ArgumentParser();sub=p.add_subparsers(dest='command',required=True)
 a=sub.add_parser('restore');a.add_argument('--downloads',required=True);a.add_argument('--assets',required=True);a.add_argument('--manifest-sha',required=True)
 a=sub.add_parser('verify');a.add_argument('--assets',required=True);a.add_argument('--output',required=True)
 a=sub.add_parser('run');a.add_argument('--input',required=True);a.add_argument('--assets',required=True);a.add_argument('--output',required=True);a.add_argument('--profile',choices=['native_v31','native_v321','business_v3'],default='native_v321');a.add_argument('--mode',choices=['queue','file','codex'],default='queue');a.add_argument('--analysis');a.add_argument('--batch-size',type=int,default=10)
 args=p.parse_args()
 if args.command=='restore':result=restore(args.downloads,args.assets,args.manifest_sha)
 elif args.command=='verify':result=verify_restore(args.assets,args.output)
 else:
  if not 1<=args.batch_size<=25:p.error('batch-size must be 1..25')
  if args.mode=='file' and not args.analysis:p.error('--analysis required for file mode')
  result=run(args.input,args.assets,args.output,args.profile,args.mode,args.analysis,args.batch_size)
 print(json.dumps(result,ensure_ascii=False,indent=2));return 0
if __name__=='__main__':raise SystemExit(main())
