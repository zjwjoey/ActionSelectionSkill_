"""Explicit optional model download/build; never a hidden runtime download."""
import argparse,json,sys,os
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
def main():
 p=argparse.ArgumentParser();p.add_argument('--output',required=True);p.add_argument('--model-cache',required=True);p.add_argument('--revision',required=True);a=p.parse_args()
 cache=Path(a.model_cache).resolve();cache.mkdir(parents=True,exist_ok=True)
 os.environ['HF_HOME']=str(cache);os.environ['HF_HUB_DISABLE_TELEMETRY']='1';os.environ['HF_HUB_DISABLE_XET']='1'
 from huggingface_hub import snapshot_download
 from runtime.retail.hybrid import MODEL,build
 from runtime.v3.catalog import Catalog
 path=snapshot_download(MODEL,revision=a.revision,cache_dir=str(cache),allow_patterns=['*.json','*.txt','*.safetensors','*.model','1_Pooling/*'],ignore_patterns=['onnx/*','openvino/*'])
 print(json.dumps(build(Catalog(Path(__file__).resolve().parents[1]),a.output,path,a.revision),ensure_ascii=False))
if __name__=='__main__':main()
