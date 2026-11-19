import { definePreset } from '@primeuix/themes';
import Aura from '@primeuix/themes/aura';

/**
 * Tema del panel: Aura con la paleta de Firmadoc, la misma del panel estático (`admin_ui/admin.css`).
 * Acento azul (`#1f5fbf` en claro, `#6ea3f2` en oscuro) y grises azulados para fondos, bordes y textos.
 * Es el único lugar del panel donde se escriben estos valores; el resto usa los tokens `--p-*`
 * (docs/design-system.md). El widget recibe la misma paleta con `?accent=blue`.
 */
const SURFACE = {
  0: '#ffffff',
  50: '#f6f7f9',
  100: '#e8eaee',
  200: '#d5d9e0',
  300: '#b8c0cb',
  400: '#9aa4b2',
  500: '#5b6573',
  600: '#3a4350',
  700: '#2c333d',
  800: '#232a33',
  900: '#1c2128',
  950: '#14171c',
};

export const FirmadocPreset = definePreset(Aura, {
  semantic: {
    primary: {
      50: '#eef4fd',
      100: '#d9e6fa',
      200: '#b6cff5',
      300: '#8fb6f3',
      400: '#6ea3f2',
      500: '#3f7fdc',
      600: '#1f5fbf',
      700: '#1a4f9f',
      800: '#173f7d',
      900: '#12305e',
      950: '#0b1f3d',
    },
    colorScheme: {
      light: {
        surface: SURFACE,
        primary: {
          color: '{primary.600}',
          contrastColor: '#ffffff',
          hoverColor: '{primary.700}',
          activeColor: '{primary.800}',
        },
        highlight: {
          background: '{primary.50}',
          focusBackground: '{primary.100}',
          color: '{primary.700}',
          focusColor: '{primary.800}',
        },
      },
      dark: {
        surface: SURFACE,
        primary: {
          color: '{primary.400}',
          contrastColor: '{surface.950}',
          hoverColor: '{primary.300}',
          activeColor: '{primary.200}',
        },
      },
    },
  },
});
