// Bootstrap: bind 0.0.0.0:8080 so the container is reachable in-cluster. Not exercised by the unit
// tests (they use Nest's Test harness against createNestApplication()), so it is excluded from coverage.
import { NestFactory } from '@nestjs/core';
import { AppModule } from './app.module';

async function bootstrap() {
  const app = await NestFactory.create(AppModule);
  await app.listen(8080, '0.0.0.0');
}

void bootstrap();
