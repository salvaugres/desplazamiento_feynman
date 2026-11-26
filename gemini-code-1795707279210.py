import numpy as np
import matplotlib.pyplot as plt
from scipy.integrate import quad
from scipy.special import ellipk, ellipe, j1

R = 1.0
d = 0.2 * R
z_top5d = d / 2 + 5 * d  # 5d por encima de la placa superior (z = 5.5d)


def H_wire_norm(rho, z):
    if rho < 1e-12:
        return 0.0
    t1 = (z - d / 2) / np.sqrt(rho**2 + (z - d / 2)**2)
    t2 = (z + d / 2) / np.sqrt(rho**2 + (z + d / 2)**2)
    return (R / (2.0 * rho)) * (2.0 + t1 - t2)


def phi_elliptic(rho, rhop, dz):
    if rho * rhop < 1e-18:
        return 0.0
    apb = (rho + rhop)**2 + dz**2
    m = 4.0 * rho * rhop / apb
    K, E = ellipk(m), ellipe(m)
    return (4.0 / apb**1.5) * (((2.0 - m) / m) * (E / (1.0 - m)) - (2.0 / m) * K)


def H_total_norm(rho, z):
    if rho < 1e-12:
        return 0.0
    hw = H_wire_norm(rho, z)

    def plate_int(z_p, sign):
        dz = z - z_p
        if abs(dz) < 1e-12:
            return 0.0
        pts = [rho] if rho < R else None
        res, _ = quad(
            lambda rp: (1.0 - (rp / R)**2) * phi_elliptic(rho, rp, dz),
            0.0, R, points=pts, epsabs=1e-9, epsrel=1e-9
        )
        return (R / (4.0 * np.pi)) * sign * dz * res

    return hw + plate_int(+d / 2, +1.0) + plate_int(-d / 2, -1.0)


rho_all = np.linspace(0.0, 3.0, 180)
rho_in = np.linspace(0.0, 1.0, 100)
rho_pos = rho_all[rho_all >= 0.22]

H_mid = [H_total_norm(r, 0.0) for r in rho_all]
H_5d = [H_total_norm(r, z_top5d) for r in rho_pos]
H_inf = 1.0 / rho_pos
H_ideal = np.where(rho_all <= 1.0, rho_all, 1.0 / np.maximum(rho_all, 1e-9))

H_bessel_15 = j1(1.5 * rho_in) / j1(1.5)
H_bessel_24 = j1(2.4 * rho_in) / j1(2.4)

fig, ax = plt.subplots(figsize=(9.5, 5.6))

ax.axvline(1.0, color='gray', linestyle=':', linewidth=1.2, alpha=0.8)
ax.axvspan(0.0, 1.0, color='#3974b8', alpha=0.07, label='Interior placas ($\\rho \\leq R$)')

ax.plot(rho_pos, H_inf, 'k--', linewidth=1.6, label=r'Hilo infinito $I/(2\pi\rho)$')
ax.plot(rho_all, H_ideal, color='#7f8c8d', linestyle='-.', linewidth=1.5, label=r'Ideal sin bordes ($d \to 0, kR \to 0$)')
ax.plot(rho_all, H_mid, color='#e74c3c', linewidth=2.3, label=r'$z = 0$ (cuasiestático, $d = 0.2R$)')
ax.plot(rho_pos, H_5d, color='#2980b9', linewidth=2.0, label=r'$z = 5.5d$ ($5d$ sobre placa)')
ax.plot(rho_in, H_bessel_15, color='#27ae60', linewidth=2.2, label=r'Bessel $J_1(k\rho)/J_1(kR)$, $kR = 1.5$')
ax.plot(rho_in, H_bessel_24, color='#8e44ad', linewidth=2.2, label=r'Bessel $J_1(k\rho)/J_1(kR)$, $kR = 2.4$')

ax.set_xlim(0.0, 3.0)
ax.set_ylim(0.0, 2.2)
ax.set_xlabel(r'Radio normalizado $\rho / R$', fontsize=12)
ax.set_ylabel(r'Campo magnético normalizado $H_\phi \,/\, (I / 2\pi R)$', fontsize=12)
ax.set_title(r'Perfil radial de $H_\phi(\rho, z)$: cuasiestático ($d=0.2R$) vs. alta frecuencia (Bessel)', fontsize=12.5, weight='bold')
ax.grid(True, linestyle='--', alpha=0.35)
ax.legend(loc='upper right', fontsize=9.5, framealpha=0.95)

plt.tight_layout()
plt.savefig('perfil_radial_bessel.pdf', dpi=300)
plt.savefig('perfil_radial_bessel.png', dpi=300)
plt.show()