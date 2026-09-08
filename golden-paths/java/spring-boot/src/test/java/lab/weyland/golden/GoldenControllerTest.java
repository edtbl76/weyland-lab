package lab.weyland.golden;

import static org.hamcrest.Matchers.containsString;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.get;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.content;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.jsonPath;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.status;

import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.autoconfigure.web.servlet.AutoConfigureMockMvc;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.test.web.servlet.MockMvc;

/** Golden-path self-test (Java/Spring Boot) — the lane probe + contract proof, over MockMvc. */
@SpringBootTest
@AutoConfigureMockMvc
class GoldenControllerTest {

    @Autowired
    MockMvc mvc;

    @Test
    void healthIsOk() throws Exception {
        mvc.perform(get("/health")).andExpect(status().isOk()).andExpect(jsonPath("$.status").value("ok"));
    }

    @Test
    void readyIsReady() throws Exception {
        mvc.perform(get("/ready")).andExpect(status().isOk()).andExpect(jsonPath("$.status").value("ready"));
    }

    @Test
    void helloReturnsTheKnownPayload() throws Exception {
        mvc.perform(get("/hello"))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.message").value("hello, weyland"))
                .andExpect(jsonPath("$.service").value("golden-java-spring-boot"));
    }

    @Test
    void metricsExposesPrometheus() throws Exception {
        mvc.perform(get("/hello"));
        mvc.perform(get("/metrics")).andExpect(status().isOk())
                .andExpect(content().string(containsString("golden_hello_requests_total")));
    }
}
