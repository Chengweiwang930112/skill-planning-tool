/**
 * Adapted from the Siemens Element documentation example.
 * Copyright (c) Siemens 2016 - 2026
 * SPDX-License-Identifier: MIT
 *
 * Temporary: a visual check that the theme renders the design system's button
 * variants. Not part of the application.
 */
import { Component } from '@angular/core';

@Component({
  selector: 'app-button-showcase',
  templateUrl: './button-showcase.html',
})
export class ButtonShowcase {
  protected disabled = false;
}
