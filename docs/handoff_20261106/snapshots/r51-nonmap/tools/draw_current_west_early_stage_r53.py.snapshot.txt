"""Show the adopted nine routes and the actual completed early civil stage."""
import json
from pathlib import Path
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.font_manager import FontProperties
from build_continuous_upright_directory_r52 import sample


def main():
    base = Path('D:/eva/artifacts/map_complete_20261013')
    directory = json.loads((base/'phased_routes/PHASED_MONOTONE_DESIGN.json').read_text('utf8'))
    previous = json.loads((base/'phased_routes/west_early_current/ROOT_PREVIOUS_PHASED.json').read_text('utf8'))
    assert (base/'phased_routes/west_early_current/combined_civil/APPLIED.json').exists()
    font = FontProperties(fname='C:/Windows/Fonts/msyh.ttc')
    plt.rcParams.update({'axes.unicode_minus': False, 'font.family': font.get_name()})
    fig, axes = plt.subplots(1, 3, figsize=(16, 6), gridspec_kw={'width_ratios': [1.25, 1, 1]})
    colors = ['#2475bd', '#db8032', '#7855ae']; styles = ['-', '--', ':']
    for leg in directory['legs']:
        if leg['id'].endswith('/reverse') or 'centre_curve' not in leg: continue
        variant, bank = int(leg['id'][4]), int(leg['id'].split('/')[1][-1])
        points = np.concatenate([sample(s['controls'], 120) for s in leg['centre_curve']['segments']])
        axes[0].plot(-points[:, 2], points[:, 1], color=colors[bank-1], ls=styles[variant], lw=1.4,
            label=f'{bank}号区 / {variant}号机')
        if bank != 3: continue
        early = np.concatenate([sample(s['controls'], 120) for s in leg['centre_curve']['segments'][:3]])
        axes[1].plot(early[:, 0], -early[:, 2], color=colors[variant], lw=2.4, label=f'{variant}号机当前曲线')
        axes[2].plot(-early[:, 2], early[:, 1], color=colors[variant], lw=2.4)
        old = next(l for l in previous['legs'] if l['id'] == leg['id'])
        old_points = np.concatenate([sample(s['controls'], 100) for s in old['centre_curve']['segments'][:4]])
        axes[1].plot(old_points[:, 0], -old_points[:, 2], color=colors[variant], alpha=.3, lw=1, ls='--')
        axes[2].plot(-old_points[:, 2], old_points[:, 1], color=colors[variant], alpha=.3, lw=1, ls='--')
        stop = np.array(leg['centre_curve']['segments'][0]['controls'][-1])
        axes[2].scatter([-stop[2]], [stop[1]], color=colors[variant], s=28)
    axes[0].set(xlabel='向北距离 −Z / m', ylabel='机体脚位 Y / m', title='九条当前发射通道（侧向投影）')
    axes[0].legend(fontsize=8, ncol=2, loc='upper left')
    axes[1].set(xlabel='X / m（西 ←）', ylabel='向北距离 −Z / m', title='三号区早段向西展开（俯视）')
    axes[1].legend(fontsize=9, loc='upper left'); axes[1].set_aspect('equal', adjustable='datalim')
    axes[2].set(xlabel='向北距离 −Z / m', ylabel='机体脚位 Y / m', title='先垂直 86m，再连续斜升')
    axes[2].annotate('原垂直段终点 Y = −944', xy=(-28.3, -944), xytext=(8, -996), arrowprops={'arrowstyle': '->', 'color': '#55616c'}, fontsize=9)
    for ax in axes:
        ax.grid(alpha=.2); ax.spines[['right', 'top']].set_visible(False)
    fig.suptitle('已施工：三路西展开早段 + 反角头边沿；完整退役旧早段空腔', fontsize=15, y=.98)
    fig.text(.04, .025, '实写并回读：1,865,823 格；旧空腔恢复 444,183 格。虚线为已退役旧早段。1872 锚点 / 三处上部门拟合已生成，原生动态检查待进行。', fontsize=10)
    fig.tight_layout(rect=[0, .07, 1, .94])
    output = base/'design_reviews/west-early-nine-routes-current.png'; output.parent.mkdir(exist_ok=True)
    fig.savefig(output, dpi=170); print(output)


if __name__ == '__main__': main()
