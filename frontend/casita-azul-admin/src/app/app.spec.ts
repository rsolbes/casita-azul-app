import { TestBed } from '@angular/core/testing';
import { AppComponent } from './app.component'; // 👈 ARREGLADO

describe('AppComponent', () => {
  beforeEach(async () => {
    await TestBed.configureTestingModule({
      imports: [AppComponent], // 👈 ARREGLADO
    }).compileComponents();
  });

  it('should create the app', () => {
    const fixture = TestBed.createComponent(AppComponent); // 👈 ARREGLADO
    const app = fixture.componentInstance;
    expect(app).toBeTruthy();
  });

  it('should have the title', () => {
    const fixture = TestBed.createComponent(AppComponent); // 👈 ARREGLADO
    const app = fixture.componentInstance;
    expect(app.title).toEqual('casita-azul-admin'); // 👈 ARREGLADO
  });
});
