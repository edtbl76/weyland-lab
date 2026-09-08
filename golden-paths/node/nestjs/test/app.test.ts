// Contract self-test (NestJS). Boots the real module via Nest's Test harness and drives the four
// endpoints over supertest against the in-memory HTTP server. Named *.test.ts (not *.spec.ts) so the
// CI lane's *.test.ts discovery glob finds this project's root.
import { Test } from '@nestjs/testing';
import { INestApplication } from '@nestjs/common';
import request from 'supertest';
import { AppModule } from '../src/app.module';
import { SERVICE_NAME } from '../src/app.controller';

describe('golden-node-nestjs contract', () => {
  let app: INestApplication;

  beforeAll(async () => {
    const moduleRef = await Test.createTestingModule({ imports: [AppModule] }).compile();
    app = moduleRef.createNestApplication();
    await app.init();
  });

  afterAll(async () => {
    await app.close();
  });

  it('health is ok', async () => {
    const res = await request(app.getHttpServer()).get('/health');
    expect(res.status).toBe(200);
    expect(res.body.status).toBe('ok');
  });

  it('ready is ready', async () => {
    const res = await request(app.getHttpServer()).get('/ready');
    expect(res.status).toBe(200);
    expect(res.body.status).toBe('ready');
  });

  it('hello returns the known payload', async () => {
    const res = await request(app.getHttpServer()).get('/hello');
    expect(res.status).toBe(200);
    expect(res.body).toEqual({ service: SERVICE_NAME, message: 'hello, weyland' });
  });

  it('metrics exposes prometheus', async () => {
    await request(app.getHttpServer()).get('/hello');
    const res = await request(app.getHttpServer()).get('/metrics');
    expect(res.status).toBe(200);
    expect(res.text).toContain('golden_hello_requests_total');
  });
});
