import subprocess
import time
import json
from pathlib import Path
import pandas as pd


def _write_config(overrides: dict):
    cfg_path = Path('config.json')
    with cfg_path.open('r', encoding='utf-8') as f:
        cfg = json.load(f)
    cfg.update(overrides)
    with cfg_path.open('w', encoding='utf-8') as f:
        json.dump(cfg, f, indent=4)


def _compute_metrics(sent_path='sent_messages.csv', rec_path='all_devices_recorded_data.csv'):
    sent = pd.read_csv(sent_path) if Path(sent_path).exists() else pd.DataFrame(columns=['device_id','send_ts','protocol'])
    rec = pd.read_csv(rec_path) if Path(rec_path).exists() else pd.DataFrame()
    protocols = sorted(sent['protocol'].unique()) if not sent.empty else []
    results = []
    for proto in protocols:
        sent_count = int((sent[sent['protocol'] == proto]).shape[0])
        if not rec.empty:
            rec_proto = rec[rec['protocol'] == proto]
            rec_count = int(rec_proto.shape[0])
            if 'latency_ms' in rec_proto.columns:
                lat = pd.to_numeric(rec_proto['latency_ms'], errors='coerce').dropna()
                avg_latency = float(lat.mean()) if not lat.empty else None
            else:
                avg_latency = None
        else:
            rec_count = 0
            avg_latency = None
        pdr = rec_count / sent_count if sent_count > 0 else None
        results.append({'protocol': proto, 'sent': sent_count, 'received': rec_count, 'pdr': pdr, 'avg_latency_ms': avg_latency})
    return results


def run_sweep(loss_rates, fail_probs, run_seconds=12, output_csv='experiments_results.csv'):
    out_rows = []
    base_cfg_path = Path('config.json')
    if not base_cfg_path.exists():
        raise FileNotFoundError('config.json missing')

    for loss in loss_rates:
        for fail in fail_probs:
            print(f'Running experiment loss={loss} fail={fail}')
            # reset logs
            for p in ['all_devices_recorded_data.csv', 'sent_messages.csv']:
                try:
                    Path(p).unlink()
                except Exception:
                    pass
            # write config overrides
            _write_config({'loss_rate': loss, 'fail_prob': fail})
            # start demo
            proc = subprocess.Popen(["python", "run_demo.py"], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            try:
                time.sleep(run_seconds)
            finally:
                # terminate process
                proc.terminate()
                try:
                    proc.wait(timeout=3)
                except Exception:
                    proc.kill()
            # compute metrics
            metrics = _compute_metrics()
            for m in metrics:
                row = {'loss_rate': loss, 'fail_prob': fail, **m}
                out_rows.append(row)
            # small pause
            time.sleep(1)

    if out_rows:
        df = pd.DataFrame(out_rows)
        df.to_csv(output_csv, index=False)
    return out_rows


if __name__ == '__main__':
    # quick demo sweep
    run_sweep([0.0, 0.1], [0.0, 0.05], run_seconds=12)
