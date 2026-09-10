import { Component } from '@angular/core';
import { greeting } from './greeting';

@Component({
  selector: 'app-root',
  imports: [],
  templateUrl: './app.component.html',
})
export class AppComponent {
  message = greeting();
}
