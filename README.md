<div align="center">
  <img src=".github/resources/logo.png" height="180px" width="auto" alt="rss temple logo">
  <br />
  <h2 style="font-size: 32px;">
    RSS Temple
  </h2>

  <h3 style="font-size: 25px;">
    A fast, powerful, self-hostable RSS reader.
  </h3>
  <br/>

[![license-badge-img]][license-badge]
[![release-badge-img]][release-badge]
[![Docker][docker-pulls-badge-img]][docker-pulls-badge]
[![CircleCI][circleci-badge-img]][circleci-badge]
[![codecov][codecov-badge-img]][codecov-badge]

  </div>
</div>

# Table of Contents

- [Table of Contents](#table-of-contents)
- [Overview](#overview)
  - [Features](#features)
  - [Preview](#preview)
- [Installation](#installation)
- [Technical Support](#technical-support)
- [Project Support](#project-support)

# Overview

RSS Temple is a fast, powerful, and self-hostable RSS/Atom reader, with a light, clean UI, and powerful subscription and search features.

It was original written as a personal attempt to reproduce the feeling of [Google Reader](https://en.wikipedia.org/wiki/Google_Reader), but with some of the features that I liked from [Feedly](https://feedly.com), without needing to pay the subscription cost.

The official deployment of this project is at [rsstemple.com](https://rsstemple.com), but I have no issue with this project being forked or redeployed.

It is made up of 3 projects - a landing page, an app frontend, and an app backend.

The landing page code can be found [here](https://github.com/murrple-1/rss_temple_ui/tree/master/rss-temple-home).

The app frontend code can be found [here](https://github.com/murrple-1/rss_temple_ui/tree/master/rss-temple-web-app).

The backend code can be found [here](https://github.com/murrple-1/rss_temple).

Additionally, there is an Ansible collection (code available [here](https://github.com/murrple-1/ansible-collection-rss-temple), Ansible Galaxy deployment [here](https://galaxy.ansible.com/ui/repo/published/murrple_1/rss_temple/)) and a Terraform project (available [here](https://github.com/murrple-1/terraform-rss-temple)) which are intended to make deployment as easy as possible.

## Features

- Subscribe to any RSS or Atom feed
- Can't find the feed URL? No problem, RSS Temple will find it for you
- Fast, full-text search
- Keyboard shortcuts

## Preview

|                                       🖥 Desktop                                       |                                                           📱 Mobile                                                            |
| :------------------------------------------------------------------------------------: | :----------------------------------------------------------------------------------------------------------------------------: |
| <img src=".github/resources/screenshots/preview-desktop.png" alt="desktop preview" /> | <img style="width: 500px; aspect-ratio: auto;" src=".github/resources/screenshots/preview-mobile.png" alt="mobile preview" /> |
| <img src=".github/resources/screenshots/preview-desktop-dark.png" alt="desktop preview dark" /> | <img style="width: 500px; aspect-ratio: auto;" src=".github/resources/screenshots/preview-mobile-dark.png" alt="mobile preview dark" /> |

# Installation

## Ansible (recommended)

Assuming you want to install everything on your current (local) machine:

```bash
ansible-galaxy collection install murrple_1.rss_temple
ansible-playbook --connection=local --inventory localhost, murrple_1.rss_temple.pre_rss_temple
ansible-playbook --connection=local --inventory localhost, murrple_1.rss_temple.rss_temple
ansible-playbook --connection=local --inventory localhost, murrple_1.rss_temple.rss_temple_home
ansible-playbook --connection=local --inventory localhost, murrple_1.rss_temple.rss_temple_web_app
```

## Manual

*TODO write this part*

# Technical Support

If you have any issues with RSS Temple, please [open an issue](https://github.com/murrple-1/rss_temple/issues/new) in this repository.

# Project Support

Consider supporting the development of this project on Ko-Fi. All funds will be used to cover the costs of hosting, development, and maintenance of RSS Temple.

<a href="https://ko-fi.com/murraychristopherson">
  <img src="https://storage.ko-fi.com/cdn/brandasset/v2/support_me_on_kofi_badge_red.png" width="150" height="auto" alt="Ko-Fi">
</a>

[license-badge-img]: https://img.shields.io/github/license/murrple-1/rss_temple?style=for-the-badge&color=a32d2a
[license-badge]: LICENSE
[release-badge-img]: https://img.shields.io/github/v/release/murrple-1/rss_temple?style=for-the-badge
[release-badge]: https://github.com/murrple-1/rss_temple/releases
[docker-pulls-badge-img]: https://img.shields.io/docker/pulls/murraychristopherson/rss_temple?style=for-the-badge&label=pulls
[docker-pulls-badge]: https://hub.docker.com/r/murraychristopherson/rss_temple
[circleci-badge-img]: https://img.shields.io/circleci/build/github/murrple-1/rss_temple?style=for-the-badge
[circleci-badge]: https://dl.circleci.com/status-badge/redirect/gh/murrple-1/rss_temple/tree/master
[codecov-badge-img]: https://img.shields.io/codecov/c/github/murrple-1/rss_temple?style=for-the-badge
[codecov-badge]: https://codecov.io/gh/murrple-1/rss_temple
