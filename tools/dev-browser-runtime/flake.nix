{
  description = "Pinned Linux runtime libraries for the HLA Playwright browser";

  inputs.nixpkgs.url = "github:NixOS/nixpkgs/nixos-26.05";

  outputs = { nixpkgs, ... }:
    let
      system = "x86_64-linux";
      pkgs = import nixpkgs { inherit system; };
      runtimePackages = [
        { name = "alsa-lib"; package = pkgs.alsa-lib; }
        { name = "at-spi2-atk"; package = pkgs.at-spi2-atk; }
        { name = "at-spi2-core"; package = pkgs.at-spi2-core; }
        { name = "atk"; package = pkgs.atk; }
        { name = "cairo"; package = pkgs.cairo; }
        { name = "cups-lib"; package = pkgs.cups.lib; }
        { name = "dbus-lib"; package = pkgs.dbus.lib; }
        { name = "expat"; package = pkgs.expat; }
        { name = "fontconfig"; package = pkgs.fontconfig; }
        { name = "freetype"; package = pkgs.freetype; }
        { name = "glib"; package = pkgs.glib.out; }
        { name = "gtk3"; package = pkgs.gtk3; }
        { name = "libdrm"; package = pkgs.libdrm; }
        { name = "libgbm"; package = pkgs.libgbm; }
        { name = "libxkbcommon"; package = pkgs.libxkbcommon; }
        { name = "mesa"; package = pkgs.mesa; }
        { name = "nspr"; package = pkgs.nspr; }
        { name = "nss"; package = pkgs.nss; }
        { name = "pango"; package = pkgs.pango; }
        { name = "systemd"; package = pkgs.systemd; }
        { name = "x11"; package = pkgs.libx11; }
        { name = "xcomposite"; package = pkgs.libxcomposite; }
        { name = "xdamage"; package = pkgs.libxdamage; }
        { name = "xext"; package = pkgs.libxext; }
        { name = "xfixes"; package = pkgs.libxfixes; }
        { name = "xi"; package = pkgs.libxi; }
        { name = "xcursor"; package = pkgs.libxcursor; }
        { name = "xrandr"; package = pkgs.libxrandr; }
        { name = "xrender"; package = pkgs.libxrender; }
        { name = "xscrnsaver"; package = pkgs.libxscrnsaver; }
        { name = "xtst"; package = pkgs.libxtst; }
        { name = "xcb"; package = pkgs.libxcb; }
        { name = "xshmfence"; package = pkgs.libxshmfence; }
        { name = "gcc-runtime"; package = pkgs.stdenv.cc.cc.lib; }
      ];
      assetPackages = [
        {
          name = "fontconfig-config";
          archive = pkgs.fetchurl {
            url = "https://archive.ubuntu.com/ubuntu/pool/main/f/fontconfig/fontconfig-config_2.15.0-1.1ubuntu2_amd64.deb";
            sha256 = "9df0579cd298a1f2b7a40efd519c849745aecd193a09733cf4d1032284a62bbf";
          };
        }
        {
          name = "fonts-freefont-ttf";
          archive = pkgs.fetchurl {
            url = "https://archive.ubuntu.com/ubuntu/pool/main/f/fonts-freefont/fonts-freefont-ttf_20211204+svn4273-2_all.deb";
            sha256 = "c8283ec9ca390e6ad8d2114cb0942182db62bb97f5142c2f955218fc5f2027b4";
          };
        }
        {
          name = "fonts-ipafont-gothic";
          archive = pkgs.fetchurl {
            url = "https://archive.ubuntu.com/ubuntu/pool/universe/f/fonts-ipafont/fonts-ipafont-gothic_00303-21ubuntu1_all.deb";
            sha256 = "71e63f0f88cca672fbb24ed27873d799d8c37233f001aa0bbcdc2f303b1b98a2";
          };
        }
        {
          name = "fonts-liberation";
          archive = pkgs.fetchurl {
            url = "https://archive.ubuntu.com/ubuntu/pool/main/f/fonts-liberation/fonts-liberation_2.1.5-3_all.deb";
            sha256 = "065c2ab1abc9108b17d401016dc594b79750904390f095845c93bb06e1153acc";
          };
        }
        {
          name = "fonts-noto-color-emoji";
          archive = pkgs.fetchurl {
            url = "https://archive.ubuntu.com/ubuntu/pool/main/f/fonts-noto-color-emoji/fonts-noto-color-emoji_2.047-0ubuntu0.24.04.1_all.deb";
            sha256 = "b102b62ce6a7313315223cff5e052bdf8fc0ad162c9e961ce0dc2202bc139ce2";
          };
        }
        {
          name = "fonts-tlwg-loma-otf";
          archive = pkgs.fetchurl {
            url = "https://archive.ubuntu.com/ubuntu/pool/universe/f/fonts-tlwg/fonts-tlwg-loma-otf_0.7.3-1_all.deb";
            sha256 = "888038637a15d11993e3a9ddd50f6391a704918b2e38fe75b2f4d74b4fcfda9a";
          };
        }
        {
          name = "fonts-unifont";
          archive = pkgs.fetchurl {
            url = "https://archive.ubuntu.com/ubuntu/pool/universe/u/unifont/fonts-unifont_15.1.01-1build1_all.deb";
            sha256 = "56c9d46ce8223fa29c28eaeb99cabfc3a3159d3eec58f0bbbea839953f4cf363";
          };
        }
        {
          name = "fonts-urw-base35";
          archive = pkgs.fetchurl {
            url = "https://archive.ubuntu.com/ubuntu/pool/main/f/fonts-urw-base35/fonts-urw-base35_20200910-8_all.deb";
            sha256 = "46e75490faa7fd6fddbc8df234d14e0f7b60ea5e98563227a24d6bf5e5008647";
          };
        }
        {
          name = "fonts-wqy-zenhei";
          archive = pkgs.fetchurl {
            url = "https://archive.ubuntu.com/ubuntu/pool/universe/f/fonts-wqy-zenhei/fonts-wqy-zenhei_0.9.45-8_all.deb";
            sha256 = "496969d65dc5664a3291e678d5cbef6815dc308ee5bf37b656c00af2cb490410";
          };
        }
        {
          name = "xfonts-base";
          archive = pkgs.fetchurl {
            url = "https://archive.ubuntu.com/ubuntu/pool/main/x/xfonts-base/xfonts-base_1.0.5+nmu1_all.deb";
            sha256 = "5fbb9f9e954cdde7a5c1b1c3b6c1fe3b4bf4a3aedc952b7b9745afe5dd9dc1eb";
          };
        }
        {
          name = "xfonts-cyrillic";
          archive = pkgs.fetchurl {
            url = "https://archive.ubuntu.com/ubuntu/pool/universe/x/xfonts-cyrillic/xfonts-cyrillic_1.0.5+nmu1_all.deb";
            sha256 = "d4a63d4da9f6d58467ccaa22b7b26c009ab46b07f0b1be2138d3bb037e74d2cb";
          };
        }
        {
          name = "xfonts-encodings";
          archive = pkgs.fetchurl {
            url = "https://archive.ubuntu.com/ubuntu/pool/main/x/xfonts-encodings/xfonts-encodings_1.0.5-0ubuntu2_all.deb";
            sha256 = "3bac5ff1cba3b001aee1652e3af45d200c415b68e9b27932cb51fe9c464feb40";
          };
        }
        {
          name = "xfonts-scalable";
          archive = pkgs.fetchurl {
            url = "https://archive.ubuntu.com/ubuntu/pool/main/x/xfonts-scalable/xfonts-scalable_1.0.3-1.3_all.deb";
            sha256 = "517f73a4f6e37332addffe6ff1795d5371f2f9c0863781efc31c4613f69993de";
          };
        }
        {
          name = "xfonts-utils";
          archive = pkgs.fetchurl {
            url = "https://archive.ubuntu.com/ubuntu/pool/main/x/xfonts-utils/xfonts-utils_7.7+6build3_amd64.deb";
            sha256 = "8da5fccbc50005d50dd69ef558ae72673435026e1d3134d0c1cc836d22953c44";
          };
        }
      ];
      packageCommands = pkgs.lib.concatMapStringsSep "\n" (entry: ''
        mkdir -p "$out/lib/${entry.name}"
        if [ -d "${entry.package}/lib" ]; then
          find -L "${entry.package}/lib" -type f -print0 | while IFS= read -r -d "" source_file; do
            relative_path="''${source_file#"${entry.package}/lib/"}"
            mkdir -p "$out/lib/${entry.name}/$(dirname "$relative_path")"
            cp -pL "$source_file" "$out/lib/${entry.name}/$relative_path"
          done
        fi
      '') runtimePackages;
      assetCommands = pkgs.lib.concatMapStringsSep "\n" (entry: ''
        package_root="$TMPDIR/${entry.name}"
        mkdir -p "$package_root"
        ${pkgs.dpkg}/bin/dpkg-deb -x "${entry.archive}" "$package_root"
        if [ -d "$package_root/usr/share/fonts" ]; then
          mkdir -p "$out/assets/usr/share/fonts"
          cp -a "$package_root/usr/share/fonts/." "$out/assets/usr/share/fonts/"
        fi
        if [ -d "$package_root/usr/share/fontconfig" ]; then
          mkdir -p "$out/assets/usr/share/fontconfig"
          cp -a "$package_root/usr/share/fontconfig/." "$out/assets/usr/share/fontconfig/"
        fi
        if [ -d "$package_root/etc/fonts" ]; then
          mkdir -p "$out/assets/etc/fonts"
          cp -a "$package_root/etc/fonts/." "$out/assets/etc/fonts/"
        fi
        copyright_file="$package_root/usr/share/doc/${entry.name}/copyright"
        if [ -f "$copyright_file" ]; then
          mkdir -p "$out/assets/licenses"
          cp "$copyright_file" "$out/assets/licenses/${entry.name}.copyright"
        fi
      '') assetPackages;
    in {
      packages.${system}.default = pkgs.runCommand "hla-playwright-runtime" {
        nativeBuildInputs = [ pkgs.dpkg ];
      } ''
        mkdir -p "$out"
        ${packageCommands}
        ${assetCommands}
      '';
    };
}
